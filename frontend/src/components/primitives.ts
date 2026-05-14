type TitleOptions = {
	/**
	 * Override or extend the default typography classes.
	 */
	className?: string;
	/**
	 * Control the font-size scale used for the title.
	 */
	size?: "sm" | "md" | "lg";
};

const TITLE_SIZE_MAP: Record<Required<TitleOptions>["size"], string> = {
	sm: "text-2xl sm:text-3xl lg:text-4xl",
	md: "text-3xl sm:text-4xl lg:text-5xl",
	lg: "text-4xl sm:text-5xl lg:text-6xl",
};

/**
 * Utility helper that returns the tailwind classes for prominent page titles.
 * Accepts optional overrides to keep the API flexible for future pages.
 */
export const title = ({ className, size = "md" }: TitleOptions = {}): string => {
	const base = "font-semibold tracking-tight text-white";
	const sizeClasses = TITLE_SIZE_MAP[size];
	return [base, sizeClasses, className].filter(Boolean).join(" ");
};

/**
 * Secondary heading style to complement `title` when needed.
 */
export const subtitle = (className?: string): string => {
	const base = "text-base text-slate-300 sm:text-lg";
	return className ? `${base} ${className}` : base;
};
