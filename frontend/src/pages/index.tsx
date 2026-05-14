import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@heroui/button";

import DefaultLayout from "@/layouts/default";

type FetchState = "idle" | "loading" | "success" | "error";

interface UserResponse {
  id: number;
  balance: number;
  frozen_balance: number;
  flag_awarded: boolean;
  flag_awarded_at?: string | null;
}

interface Product {
  id: number;
  name: string;
  description?: string | null;
  price: number;
  image_url?: string | null;
  owned_quantity: number;
  max_per_user?: number | null;
}

interface Purchase {
  id: number;
  product: Product;
  quantity: number;
  total_price: number;
  created_at: string;
  status: "pending" | "confirmed" | "cancelled";
  processed_at?: string | null;
}

interface OrderResponse {
  user: UserResponse;
  purchase: Purchase;
  reward?: Reward | null;
}

interface PendingPurchaseResponse {
  purchase: Purchase | null;
}

interface Reward {
  name: string;
  message: string;
}

type AlertState =
  | {
      type: "success" | "error";
      message: string;
    }
  | null;

const TOKEN_STORAGE_KEY = "planner_token";

const extractErrorMessage = async (response: Response) => {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      return data.detail;
    }
    if (typeof data?.message === "string") {
      return data.message;
    }
  } catch {
  }

  return response.statusText || "Произошла неизвестная ошибка.";
};

const StorePage = () => {
  const [searchParams] = useSearchParams();
  const queryToken = searchParams.get("token");

  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  });

  const [status, setStatus] = useState<FetchState>("idle");
  const [productsStatus, setProductsStatus] = useState<FetchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [purchaseAlert, setPurchaseAlert] = useState<AlertState>(null);
  const [purchasingProductId, setPurchasingProductId] = useState<number | null>(
    null,
  );
  const [pendingPurchase, setPendingPurchase] = useState<Purchase | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const lastPendingRef = useRef<Purchase | null>(null);

  const apiBase = useMemo(() => {
    const fromEnv =
      (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
    if (fromEnv) {
      return fromEnv.endsWith("/") ? fromEnv.slice(0, -1) : fromEnv;
    }

    if (typeof window !== "undefined") {
      const url = new URL(window.location.origin);

      if (url.port === "5173" || url.port === "4173") {
        url.port = "8000";
      }

      return url.origin;
    }

    return "http://localhost:8000";
  }, []);

  const makeUrl = useCallback(
    (path: string) => (apiBase ? `${apiBase}${path}` : path),
    [apiBase],
  );

  useEffect(() => {
    if (!queryToken) {
      return;
    }

    setToken(queryToken);
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_STORAGE_KEY, queryToken);
    }
  }, [queryToken]);

  useEffect(() => {
    if (!purchaseAlert) {
      return;
    }

    const timer = window.setTimeout(() => setPurchaseAlert(null), 4000);
    return () => window.clearTimeout(timer);
  }, [purchaseAlert]);

  const fetchUser = useCallback(async () => {
    if (!token) {
      setStatus("error");
      setError("Токен доступа не найден.");
      return;
    }

    setStatus("loading");
    setError(null);

    try {
      const response = await fetch(makeUrl("/auth/verify"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response));
      }

      const data: UserResponse = await response.json();
      setUser(data);
      setStatus("success");
      setLastUpdated(new Date());
    } catch (err) {
      setStatus("error");
      setUser(null);
      setLastUpdated(null);
      setError(
        err instanceof Error
          ? err.message
          : "Не удалось получить данные. Попробуйте ещё раз позже.",
      );
    }
  }, [makeUrl, token]);

  const fetchProducts = useCallback(async () => {
    if (!token) {
      setProductsStatus("error");
      setProductsError("Токен доступа не найден.");
      return;
    }

    setProductsStatus("loading");
    setProductsError(null);

    try {
      const response = await fetch(makeUrl("/products"), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response));
      }

      const data: Product[] = await response.json();
      setProducts(data);
      setProductsStatus("success");
    } catch (err) {
      setProductsStatus("error");
      setProducts([]);
      setProductsError(
        err instanceof Error
          ? err.message
          : "Не удалось загрузить каталог. Попробуйте ещё раз позже.",
      );
    }
  }, [makeUrl, token]);

  const refreshUserData = useCallback(async () => {
    if (!token) {
      return;
    }

    try {
      const response = await fetch(makeUrl("/users/me"), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response));
      }

      const data: UserResponse = await response.json();
      setUser(data);
      setLastUpdated(new Date());
    } catch (err) {
      setPurchaseAlert({
        type: "error",
        message:
          err instanceof Error
            ? err.message
            : "Не удалось обновить данные аккаунта.",
      });
    }
  }, [makeUrl, token]);

  const fetchPendingPurchase = useCallback(async () => {
    if (!token) {
      setPendingPurchase(null);
      return;
    }

    try {
      const response = await fetch(makeUrl("/orders/pending"), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        return;
      }

      const data: PendingPurchaseResponse = await response.json();
      setPendingPurchase(data.purchase);
    } catch {
      /* ignore transient pending errors */
    }
  }, [makeUrl, token]);

  const handlePurchase = useCallback(
    async (productId: number) => {
      if (!token) {
        setPurchaseAlert({
          type: "error",
          message: "Токен доступа не найден.",
        });
        return;
      }

      setPurchasingProductId(productId);
      setPurchaseAlert(null);

      try {
        const response = await fetch(makeUrl("/orders"), {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ product_id: productId }),
        });

        if (!response.ok) {
          throw new Error(await extractErrorMessage(response));
        }

        const data: OrderResponse = await response.json();
        const purchasedProduct = data.purchase?.product;
        const priceLabel = purchasedProduct
          ? `${purchasedProduct.price.toLocaleString("ru-RU")} ₽`
          : "— ₽";

        setPendingPurchase(data.purchase);
        lastPendingRef.current = data.purchase;

        setPurchaseAlert({
          type: "success",
          message: `Заявка создана: ${
            purchasedProduct?.name ?? "товар"
          } на ${priceLabel}. Подтвердите покупку в боте командой /submit.`,
        });

        setUser(data.user);
        setLastUpdated(
          data.purchase?.created_at
            ? new Date(data.purchase.created_at)
            : new Date(),
        );
        void fetchProducts();
      } catch (err) {
        setPurchaseAlert({
          type: "error",
          message:
            err instanceof Error
              ? err.message
              : "Не удалось провести покупку. Попробуйте ещё раз позже.",
        });
      } finally {
        setPurchasingProductId(null);
      }
    },
    [fetchProducts, makeUrl, token],
  );

  const handleCancelPending = useCallback(async () => {
    if (!token || !pendingPurchase) {
      return;
    }

    setIsCancelling(true);
    try {
      const response = await fetch(makeUrl("/orders/cancel"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response));
      }

      const data: OrderResponse = await response.json();
      setPendingPurchase(null);
      lastPendingRef.current = null;
      setUser(data.user);
      setLastUpdated(
        data.purchase?.processed_at
          ? new Date(data.purchase.processed_at)
          : new Date(),
      );
      setPurchaseAlert({
        type: "success",
        message: "Заявка отменена. Средства разморожены.",
      });
      void fetchProducts();
    } catch (err) {
      setPurchaseAlert({
        type: "error",
        message:
          err instanceof Error
            ? err.message
            : "Не удалось отменить заявку. Попробуйте ещё раз позже.",
      });
    } finally {
      setIsCancelling(false);
    }
  }, [fetchProducts, makeUrl, pendingPurchase, token]);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setProducts([]);
      setPendingPurchase(null);
      return;
    }

    void fetchUser();
    void fetchProducts();
  }, [fetchProducts, fetchUser, token]);

  useEffect(() => {
    if (!token) {
      setPendingPurchase(null);
      return;
    }

    void fetchPendingPurchase();
  }, [fetchPendingPurchase, token]);

  useEffect(() => {
    if (!pendingPurchase || !token) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void fetchPendingPurchase();
    }, 4000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [fetchPendingPurchase, pendingPurchase, token]);

  useEffect(() => {
    if (pendingPurchase) {
      lastPendingRef.current = pendingPurchase;
      return;
    }

    if (lastPendingRef.current) {
      const last = lastPendingRef.current;
      lastPendingRef.current = null;
      setPurchaseAlert({
        type: "success",
        message: `Заявка на ${last.product.name} обработана.`,
      });
      void refreshUserData();
      void fetchProducts();
    }
  }, [fetchProducts, pendingPurchase, refreshUserData]);

  const isUserLoading = status === "loading" || status === "idle";
  const isProductsLoading =
    productsStatus === "loading" || productsStatus === "idle";

  const formattedBalance =
    user?.balance != null
      ? `${user.balance.toLocaleString("ru-RU")} ₽`
      : "— ₽";

  const availableBalance = user
    ? Math.max(user.balance - user.frozen_balance, 0)
    : 0;
  const formattedAvailableBalance = user
    ? `${availableBalance.toLocaleString("ru-RU")} ₽`
    : "— ₽";

  const formattedFrozenBalance =
    user?.frozen_balance != null
      ? `${user.frozen_balance.toLocaleString("ru-RU")} ₽`
      : "0 ₽";

  const hasPendingPurchase = Boolean(pendingPurchase);

  const formattedUpdatedAt = lastUpdated
    ? lastUpdated.toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "только что";

  const essentials = useMemo(
    () => {
      const byName = new Map(products.map((item) => [item.name, item]));
      return [
        {
          name: "Часть флага",
          price: byName.get("Часть флага")?.price ?? 500,
          subtitle: "Фрагмент легендарного полотна",
        },
        {
          name: "Картинка",
          price: byName.get("Картинка")?.price ?? 50,
          subtitle: "Обновляйте обои хоть каждый день",
        },
        {
          name: "Видео",
          price: byName.get("Видео")?.price ?? 100,
          subtitle: "Молниеносный ролик с фирменным стилем",
        },
      ];
    },
    [products],
  );

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const owned = product.owned_quantity ?? 0;
      if (product.max_per_user == null) {
        return true;
      }
      return owned < product.max_per_user;
    });
  }, [products]);

  const flagProgress = useMemo(() => {
    const flagProduct = products.find((item) => item.name === "Часть флага");
    if (!flagProduct) {
      return null;
    }
    const required = flagProduct.max_per_user ?? null;
    const owned = flagProduct.owned_quantity ?? 0;
    if (required == null || required <= 0) {
      return null;
    }
    return {
      owned,
      required,
      remaining: Math.max(required - owned, 0),
    };
  }, [products]);

  if (!token) {
    return (
      <DefaultLayout>
        <section className="mx-auto flex min-h-[60vh] w-full max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
          <h2 className="text-2xl font-semibold text-white">Требуется доступ</h2>
          <p className="text-sm text-slate-300">
            Чтобы просматривать каталог, откройте ссылку, которую прислал Telegram-бот.
          </p>
        </section>
      </DefaultLayout>
    );
  }

  if (isUserLoading) {
    return (
      <DefaultLayout>
        <section className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col items-center justify-center gap-6 px-4 text-center">
          <div className="h-14 w-14 animate-spin rounded-full border-2 border-white/20 border-t-transparent" />
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-white">Подготавливаем магазин</h2>
            <p className="text-sm text-slate-300">
              Проверяем ваш токен и загружаем баланс аккаунта.
            </p>
          </div>
        </section>
      </DefaultLayout>
    );
  }

  if (status === "error" || !user) {
    return (
      <DefaultLayout>
        <section className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col items-center justify-center gap-6 px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-rose-500/40 bg-rose-500/10 text-lg font-semibold text-rose-200">
            !
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-white">Не удалось загрузить данные</h2>
            <p className="text-sm text-slate-300">
              {error ?? "Попробуйте обновить страницу немного позже."}
            </p>
          </div>
          <Button
            className="bg-gradient-to-r from-blue-500 to-indigo-500 px-6 font-semibold text-white shadow-[0_16px_40px_-20px_rgba(59,130,246,0.65)]"
            onPress={() => {
              void fetchUser();
            }}
          >
            Повторить попытку
          </Button>
        </section>
      </DefaultLayout>
    );
  }

  return (
    <DefaultLayout>
      {purchaseAlert && (
        <div className="pointer-events-none fixed top-24 left-1/2 z-50 w-full max-w-md -translate-x-1/2 px-4">
          <div
            className={`rounded-3xl border px-5 py-4 text-sm shadow-2xl backdrop-blur ${
              purchaseAlert.type === "success"
                ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
                : "border-rose-400/40 bg-rose-500/15 text-rose-100"
            }`}
          >
            <p className="text-base font-semibold text-white">
              {purchaseAlert.message}
            </p>
          </div>
        </div>
      )}
      <section className="relative isolate overflow-hidden px-4 py-12 sm:px-6 lg:px-8">
        <div className="absolute inset-0 -z-30 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950" />
        <div className="absolute -left-32 top-0 -z-20 h-80 w-80 rounded-full bg-sky-500/30 blur-3xl sm:h-[22rem] sm:w-[22rem]" />
        <div className="absolute right-[-120px] top-1/2 -z-20 h-96 w-96 rounded-full bg-purple-500/20 blur-3xl sm:right-[-160px]" />
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_30%,rgba(56,189,248,0.12),transparent_55%)]" />

        <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-12">
          <header className="flex flex-col gap-8 text-white md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl space-y-4">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1 text-xs uppercase tracking-[0.45em] text-sky-200/80">
                planner store
              </span>
              <h1 className="text-4xl font-semibold leading-tight sm:text-5xl">
                Соберите цифровой сет наград
              </h1>
              <p className="text-sm text-slate-300 sm:text-base">
                Получайте часть флага, эксклюзивную картинку и динамичное видео, используя баланс вашего аккаунта.
              </p>
            </div>
            <div className="grid gap-3 text-xs text-slate-300 sm:text-sm">
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                <span>Токен проверяется на сервере</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                <span>Средства замораживаются до подтверждения в боте</span>
              </div>
            </div>
          </header>

          <div className="grid gap-6 lg:grid-cols-[1.6fr,1fr]">
            <div className="relative overflow-hidden rounded-[32px] border border-white/10 bg-white/5 p-8 shadow-[0_80px_160px_-90px_rgba(59,130,246,0.55)] backdrop-blur">
              <div className="absolute -top-24 right-[-80px] h-56 w-56 rounded-full bg-sky-400/20 blur-3xl" />
              <div className="relative flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.4em] text-slate-300">
                    Текущий баланс
                  </p>
                  <p className="mt-4 text-5xl font-semibold text-white sm:text-6xl">
                    {formattedBalance}
                  </p>
                  <p className="mt-3 text-xs text-slate-400">Обновлено: {formattedUpdatedAt}</p>
                </div>
                <div className="flex flex-col gap-3 text-sm text-slate-300">
                  <Button
                    className="min-w-[180px] rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-6 py-3 text-sm font-semibold text-white shadow-[0_24px_60px_-30px_rgba(56,189,248,0.8)] transition hover:from-sky-400 hover:via-indigo-400 hover:to-purple-400"
                    onPress={() => {
                      void fetchUser();
                    }}
                  >
                    Обновить баланс
                  </Button>
                  <span className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs text-slate-300">
                    ID пользователя: <span className="font-semibold text-white">{user.id}</span>
                  </span>
                </div>
              </div>
              <div className="relative mt-8 grid gap-4 sm:grid-cols-3">
                <div className="sm:col-span-3">
                  <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                    <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/10 px-4 py-3">
                      <span>Свободно</span>
                      <span className="font-semibold text-white">{formattedAvailableBalance}</span>
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-amber-400/30 bg-amber-500/15 px-4 py-3 text-amber-100">
                      <span>Заморожено</span>
                      <span className="font-semibold text-white">{formattedFrozenBalance}</span>
                    </div>
                  </div>
                  {hasPendingPurchase && (
                    <p className="mt-4 rounded-2xl border border-amber-400/30 bg-amber-500/15 px-4 py-3 text-xs text-amber-100">
                      Заявка на покупку ожидает подтверждения через Telegram-бота. После подтверждения средства спишутся автоматически.
                    </p>
                  )}
                  {!hasPendingPurchase && flagProgress && flagProgress.remaining > 0 && (
                    <p className="mt-4 rounded-2xl border border-sky-400/30 bg-sky-500/10 px-4 py-3 text-xs text-sky-100">
                      Частей флага собрано: <span className="font-semibold text-white">{flagProgress.owned}</span>{" "}
                      из <span className="font-semibold text-white">{flagProgress.required}</span>. Осталось приобрести{" "}
                      <span className="font-semibold text-white">{flagProgress.remaining}</span>.
                    </p>
                  )}
                  {!hasPendingPurchase &&
                    flagProgress &&
                    flagProgress.remaining === 0 &&
                    user?.flag_awarded && (
                      <p className="mt-4 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-100">
                        Все части флага собраны! Бонус уже доступен в Telegram-боте.
                      </p>
                    )}
                </div>
              </div>
              <div className="relative mt-8 grid gap-4 sm:grid-cols-3">
                {essentials.map((item) => (
                  <div
                    key={item.name}
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-4 text-sm text-slate-200 shadow-[0_40px_80px_-70px_rgba(59,130,246,0.8)]"
                  >
                    <p className="text-xs uppercase tracking-[0.35em] text-sky-200/80">
                      {item.name}
                    </p>
                    <p className="mt-3 text-2xl font-semibold text-white">
                      {item.price.toLocaleString("ru-RU")} ₽
                    </p>
                    <p className="mt-2 text-xs text-slate-400">{item.subtitle}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-[32px] border border-white/10 bg-white/5 p-8 backdrop-blur">
              <p className="text-xs uppercase tracking-[0.35em] text-slate-300">Статус доступа</p>
              <div className="mt-6 space-y-4 text-sm text-slate-300">
                <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-emerald-100">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
                  Токен действителен
                </div>
                <p className="leading-relaxed">
                  Магазин Planner работает в тёмной теме и адаптируется под ваш баланс. Все покупки защищены и отображаются мгновенно.
                </p>
                <p className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-xs text-slate-400">
                  Если баланс не обновился автоматически, нажмите «Обновить баланс» или перезапросите ссылку в Telegram-боте.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 text-white">
              <div>
                <h2 className="text-2xl font-semibold">Цифровой каталог</h2>
                <p className="mt-1 text-sm text-slate-300">
                  Выберите продукт, чтобы пополнить коллекцию эксклюзивов.
                </p>
              </div>
              <Button
                className="border border-white/10 bg-white/10 px-5 text-sm font-medium text-white transition hover:bg-white/20"
                isDisabled={isProductsLoading}
                onPress={() => {
                  void fetchProducts();
                }}
              >
                {isProductsLoading ? "Обновляем..." : "Обновить каталог"}
              </Button>
            </div>

            {pendingPurchase && (
              <div className="rounded-[28px] border border-amber-400/40 bg-amber-500/10 px-6 py-6 text-amber-100 shadow-[0_60px_120px_-80px_rgba(251,191,36,0.6)]">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-2">
                    <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/40 bg-black/20 px-3 py-1 text-xs uppercase tracking-[0.3em] text-amber-200">
                      ожидание
                    </span>
                    <h3 className="text-lg font-semibold text-white">
                      Подтвердите заявку в Telegram-боте командой <span className="font-mono text-amber-200">/submit</span>
                    </h3>
                    <p className="text-sm text-amber-100/80">
                      После подтверждения средства спишутся автоматически и товар добавится в коллекцию.
                    </p>
                  </div>
                  <div className="min-w-[220px] rounded-2xl border border-amber-300/40 bg-black/25 px-4 py-3 text-sm text-white">
                    <p className="text-xs uppercase tracking-[0.3em] text-amber-200/80">Товар</p>
                    <p className="mt-2 text-base font-semibold text-white">
                      {pendingPurchase.product.name}
                    </p>
                    <p className="mt-1 text-sm text-amber-200">
                      {pendingPurchase.total_price.toLocaleString("ru-RU")} ₽ • ×{pendingPurchase.quantity}
                    </p>
                    <p className="mt-2 text-xs text-amber-200/70">
                      Оформлено: {new Date(pendingPurchase.created_at).toLocaleTimeString("ru-RU", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button
                    className="rounded-full border border-amber-300/40 bg-black/20 px-5 py-2 text-sm font-semibold text-amber-100 transition hover:border-amber-200"
                    onPress={() => {
                      void fetchPendingPurchase();
                    }}
                  >
                    Проверить статус
                  </Button>
                  <Button
                    className="rounded-full bg-amber-400 px-5 py-2 text-sm font-semibold text-black transition hover:bg-amber-300"
                    isDisabled={isCancelling}
                    onPress={() => {
                      void handleCancelPending();
                    }}
                  >
                    {isCancelling ? "Отменяем..." : "Отменить заявку"}
                  </Button>
                </div>
              </div>
            )}

            {productsStatus === "error" && (
              <div className="rounded-3xl border border-rose-400/30 bg-rose-500/15 px-6 py-4 text-sm text-rose-100">
                {productsError ?? "Не удалось загрузить товары. Попробуйте ещё раз позже."}
              </div>
            )}

            {isProductsLoading && (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-72 animate-pulse rounded-[28px] border border-white/10 bg-white/5"
                  />
                ))}
              </div>
            )}

            {productsStatus === "success" && products.length === 0 && (
              <div className="rounded-[28px] border border-white/10 bg-white/5 px-6 py-10 text-center text-sm text-slate-300">
                Сейчас нет доступных товаров. Загляните позже!
              </div>
            )}

            {productsStatus === "success" && products.length > 0 && filteredProducts.length === 0 && (
              <div className="rounded-[28px] border border-emerald-400/30 bg-emerald-500/15 px-6 py-10 text-center text-sm text-emerald-100">
                Вы уже добавили все товары в коллекцию. Ожидайте новых поступлений!
              </div>
            )}

            {productsStatus === "success" && filteredProducts.length > 0 && (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {filteredProducts.map((product) => {
                  const canAfford = availableBalance >= product.price;
                  const disablePurchase =
                    purchasingProductId === product.id || !canAfford || hasPendingPurchase;
                  return (
                    <div
                      key={product.id}
                      className="group relative flex h-full flex-col overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/70 p-6 transition duration-300 hover:border-sky-400/50 hover:shadow-[0_40px_100px_-60px_rgba(56,189,248,0.9)]"
                    >
                      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-sky-400 via-indigo-500 to-purple-500 opacity-0 transition group-hover:opacity-100" />
                      {product.image_url && (
                        <div className="mb-5 h-32 overflow-hidden rounded-2xl border border-white/5 bg-slate-900/60">
                          <img
                            alt={product.name}
                            className="h-full w-full object-cover"
                            loading="lazy"
                            src={product.image_url}
                          />
                        </div>
                      )}
                      <div className="flex flex-1 flex-col gap-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-2">
                            <h3 className="text-lg font-semibold text-white">
                              {product.name}
                            </h3>
                            <p className="text-sm text-slate-300">
                              {product.description ?? "Описание будет доступно позже."}
                            </p>
                          </div>
                          <span className="rounded-full border border-white/10 bg-white/10 px-4 py-1 text-sm font-medium text-sky-100">
                            {product.price.toLocaleString("ru-RU")} ₽
                          </span>
                        </div>
                        <Button
                          className={`mt-auto rounded-full px-6 py-2 text-sm font-semibold transition ${
                            canAfford && !hasPendingPurchase
                              ? "bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 text-white shadow-[0_20px_50px_-30px_rgba(56,189,248,0.8)] hover:from-sky-400 hover:via-indigo-400 hover:to-purple-400"
                              : "border border-white/10 bg-white/10 text-slate-400"
                          }`}
                          isDisabled={disablePurchase}
                          onPress={() => {
                            if (disablePurchase) {
                              return;
                            }
                            void handlePurchase(product.id);
                          }}
                        >
                          {purchasingProductId === product.id
                            ? "Покупаем..."
                            : hasPendingPurchase
                              ? "Ожидает подтверждения"
                              : canAfford
                                ? "Получить"
                                : "Недостаточно средств"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </section>
    </DefaultLayout>
  );
};

export default StorePage;
