import { clsx } from "clsx";
import { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: "sm" | "md" | "lg" | "none";
}

export function Card({ padding = "md", className, children, ...props }: CardProps) {
  return (
    <div
      className={clsx(
        "bg-white rounded-xl border border-gray-200 shadow-sm",
        {
          "p-3": padding === "sm",
          "p-5": padding === "md",
          "p-8": padding === "lg",
          "": padding === "none",
        },
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
