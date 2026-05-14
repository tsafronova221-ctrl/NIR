from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram import F
import httpx
import jwt

from config import get_settings
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
settings = get_settings()
router = Router()


def format_rubles(amount: int | float) -> str:
    return f"{amount:,.0f} ₽".replace(",", " ")


def format_timestamp(value: str | None) -> str:
    if not value:
        return "—"

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    return parsed.strftime("%d.%m.%Y %H:%M")


async def obtain_login_token(client: httpx.AsyncClient, user_id: int) -> str:
    response = await client.post(
        f"{settings.backend_api_base}/users/login",
        json={"user_id": user_id},
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("token")
    if not token:
        raise httpx.HTTPError("Token is missing in login response")
    return token


async def build_authorization_headers(
    client: httpx.AsyncClient, user_id: int
) -> dict[str, str]:
    token = await obtain_login_token(client, user_id)
    return {"Authorization": f"Bearer {token}"}


def build_bot_token() -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "bot": True,
        "iat": now,
        "exp": now + timedelta(minutes=1),
    }
    token: str = jwt.encode(
        payload,
        settings.bot_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    user_id = message.from_user.id
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            token = await obtain_login_token(client, user_id)
        except httpx.HTTPError:
            logger.exception("Failed to get login token for user %s", user_id)
            await message.answer(
                "Не удалось получить ссылку для входа. Попробуйте позже."
            )
            return

    link = f"{settings.frontend_base_url}?token={token}"

    await message.answer(
        (
            "Привет! Я подготовил для тебя ссылку для входа в приложение: "
            f"\n\n{link}\n\n"
            "Когда оформите покупку, подтвердите её командой /submit."
            "Также вы можете просмотреть приобретённые товары командой /products."
        ),
    )

@router.message(Command("submit"))
async def handle_submit(message: Message) -> None:
    user_id = message.from_user.id
    purchase = None
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            headers = await build_authorization_headers(client, user_id)
        except httpx.HTTPError:
            logger.exception("Failed to authorize user %s for submit", user_id)
            await message.answer(
                "Не удалось авторизоваться. Попробуйте ещё раз или запросите ссылку заново командой /start."
            )
            return

        try:
            pending_response = await client.get(
                f"{settings.backend_api_base}/orders/pending",
                headers=headers,
            )
            pending_response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to fetch pending order for user %s", user_id)
            await message.answer(
                "Не удалось проверить заявки. Попробуйте повторить позже."
            )
            return

        pending_data = pending_response.json()
        purchase = pending_data.get("purchase")

    if not purchase:
        await message.answer(
            "У вас нет заявок, ожидающих подтверждения. Оформите покупку на сайте и повторите команду /submit."
        )
        return

    product = purchase.get("product", {})
    product_name = product.get("name", "Товар")
    total_price = purchase.get("total_price", 0)
    quantity = purchase.get("quantity", 1)

    created_label = format_timestamp(purchase.get("created_at"))

    purchase_id = purchase.get("id", 0)
    total_value = str(total_price)
    product_value = str(product.get("id", ""))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"purchase:confirm:{purchase_id}:{total_value}:{product_value}",
                ),
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data=f"purchase:cancel:{purchase_id}",
                ),
            ]
        ]
    )

    await message.answer(
        (
            "Найдена заявка, ожидающая подтверждения.\n\n"
            f"Товар: <b>{product_name}</b>\n"
            f"Количество: {quantity}\n"
            f"Сумма: {format_rubles(total_price)}\n"
            f"Оформлено: {created_label}\n\n"
            "Подтвердите или отмените заявку кнопками ниже."
        ),
        reply_markup=keyboard,
    )


@router.message(Command("clear"))
async def handle_clear(message: Message) -> None:
    user_id = message.from_user.id

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            headers = await build_authorization_headers(client, user_id)
        except httpx.HTTPError:
            logger.exception("Failed to authorize user %s for clear", user_id)
            await message.answer(
                "Не удалось авторизоваться. Попробуйте позже или запросите новую ссылку через /start.",
            )
            return

        try:
            response = await client.post(
                f"{settings.backend_api_base}/users/clear",
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to clear account for user %s", user_id)
            await message.answer(
                "Не удалось очистить данные. Попробуйте повторить команду немного позже.",
            )
            return

    data = response.json()
    balance = data.get("balance", 0)
    frozen = data.get("frozen_balance", 0)

    await message.answer(
        (
            "🏁 Учётная запись очищена. Все покупки удалены, баланс сброшен."
            f"\nТекущий баланс: {format_rubles(balance)}"
            f"\nЗаморожено: {format_rubles(frozen)}"
        )
    )


@router.message(Command("products"))
async def handle_products(message: Message) -> None:
    user_id = message.from_user.id
    history_data: dict[str, object] | None = None
    profile_data: dict[str, object] | None = None

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            headers = await build_authorization_headers(client, user_id)
        except httpx.HTTPError:
            logger.exception("Failed to authorize user %s for products", user_id)
            await message.answer(
                "Не удалось авторизоваться. Попробуйте ещё раз позже или обновите ссылку командой /start."
            )
            return

        try:
            history_response = await client.get(
                f"{settings.backend_api_base}/orders/history",
                headers=headers,
            )
            history_response.raise_for_status()
            history_data = history_response.json()

            profile_response = await client.get(
                f"{settings.backend_api_base}/users/me",
                headers=headers,
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
        except httpx.HTTPError:
            logger.exception("Failed to load purchases for user %s", user_id)
            await message.answer(
                "Не удалось загрузить список покупок. Попробуйте позже."
            )
            return

    purchases: list[dict[str, object]] = []
    if isinstance(history_data, dict):
        raw = history_data.get("purchases")
        if isinstance(raw, list):
            purchases = [item for item in raw if isinstance(item, dict)]

    if not purchases:
        await message.answer(
            "Пока нет приобретённых товаров. Загляните в магазин и выберите что-нибудь интересное!"
        )
        return

    aggregated: dict[str, dict[str, float]] = {}
    for purchase in purchases:
        product = purchase.get("product") or {}
        if not isinstance(product, dict):
            product = {}

        product_name = product.get("name", "Товар")
        entry = aggregated.setdefault(
            product_name,
            {"quantity": 0, "total_price": 0.0},
        )
        quantity_value = purchase.get("quantity", 1)
        price_value = purchase.get("total_price", 0)
        if isinstance(quantity_value, (int, float, str)):
            try:
                entry["quantity"] += int(quantity_value)
            except ValueError:
                pass
        if isinstance(price_value, (int, float, str)):
            try:
                entry["total_price"] += float(price_value)
            except ValueError:
                pass

    if not aggregated:
        await message.answer(
            "Не удалось корректно обработать покупки. Попробуйте позже."
        )
        return

    lines = [
        f"• <b>{name}</b> — {info['quantity']} шт. / {format_rubles(info['total_price'])}"
        for name, info in aggregated.items()
    ]

    summary = "Ваши товары в коллекции:\n\n" + "\n".join(lines)

    if profile_data and isinstance(profile_data, dict) and profile_data.get("flag_awarded"):
        summary += "\n\n🎉 Вы собрали все части флага!"
        
        summary += f"\n\n{settings.flag}"

    await message.answer(summary)


@router.callback_query(F.data.startswith("purchase:"))
async def handle_purchase_callback(callback: CallbackQuery) -> None:
    if not callback.data:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) < 3 or parts[0] != "purchase":
        await callback.answer()
        return

    action = parts[1]
    callback_total = parts[3] if action == "confirm" and len(parts) >= 4 else None
    callback_product = parts[4] if action == "confirm" and len(parts) >= 5 else None

    user_id = callback.from_user.id

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            headers = await build_authorization_headers(client, user_id)
        except httpx.HTTPError:
            logger.exception("Failed to authorize user %s for %s", user_id, action)
            await callback.answer(
                "Не удалось авторизоваться. Попробуйте ещё раз позже.", show_alert=True
            )
            return

        try:
            pending_response = await client.get(
                f"{settings.backend_api_base}/orders/pending",
                headers=headers,
            )
            pending_response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to refresh pending order for user %s", user_id)
            await callback.answer(
                "Не удалось проверить статус заявки. Попробуйте ещё раз позже.",
                show_alert=True,
            )
            return

        pending_data = pending_response.json()
        purchase = pending_data.get("purchase")

        if not purchase:
            await callback.answer(
                "Актуальных заявок не найдено.", show_alert=True
            )
            if callback.message:
                await callback.message.edit_text(
                    "Заявка отсутствует или уже обработана.", reply_markup=None
                )
            return

        endpoint = None
        success_title = ""
        if action == "confirm":
            endpoint = "confirm"
            success_title = "Заявка подтверждена ✅"
        elif action == "cancel":
            endpoint = "cancel"
            success_title = "Заявка отменена ❌"
        else:
            await callback.answer()
            return

        try:
            confirm_headers = dict(headers)
            if callback_total is not None:
                confirm_headers["X-Planner-Locked-Amount"] = callback_total
            if action == "confirm":
                confirm_headers["X-Planner-Bot-Token"] = build_bot_token()
            if callback_product is not None:
                logger.debug(
                    "Confirm callback uses product %s for user %s",
                    callback_product,
                    user_id,
                )

            result_response = await client.post(
                f"{settings.backend_api_base}/orders/{endpoint}",
                headers=confirm_headers,
            )
            result_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Failed to %s purchase for user %s: %s",
                endpoint,
                user_id,
                exc.response.text,
            )
            if exc.response.status_code == 400:
                message_text = (
                    "Заявка не может быть обработана: проверьте баланс или повторите позже."
                )
            else:
                message_text = "Не удалось обработать заявку. Попробуйте позже."
            await callback.answer(message_text, show_alert=True)
            return
        except httpx.HTTPError:
            logger.exception("Unexpected error processing purchase for user %s", user_id)
            await callback.answer(
                "Произошла ошибка при обработке заявки. Попробуйте позже.",
                show_alert=True,
            )
            return

    result = result_response.json()
    purchase_data = result.get("purchase", {})
    user_data = result.get("user", {})
    product_data = purchase_data.get("product", {})

    product_name = product_data.get("name", "Товар")
    total_price = purchase_data.get("total_price", 0)
    balance = user_data.get("balance", 0)

    final_text = (
        f"{success_title}\n\n"
        f"Товар: <b>{product_name}</b>\n"
        f"Сумма: {format_rubles(total_price)}\n"
        f"Текущий баланс: {format_rubles(balance)}"
    )

    reward = result.get("reward")
    reward_lines: list[str] = []
    if isinstance(reward, dict):
        reward_name = reward.get("name")
        reward_text = reward.get("message")
        if reward_name:
            reward_lines.append(f"🏅 {reward_name}")
        if reward_text:
            reward_lines.append(str(reward_text))

    if reward_lines:
        final_text += "\n\n" + "\n".join(reward_lines)

    if callback.message:
        await callback.message.edit_text(final_text, reply_markup=None)

    await callback.answer("Готово!")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
