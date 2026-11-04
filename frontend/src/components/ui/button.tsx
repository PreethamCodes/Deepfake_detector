// Adapted from the shadcn/ui New York Button (MIT).
import type { ComponentProps } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const variants = cva("btn inline-flex items-center justify-center gap-2", {
  variants: {
    variant: { default: "primary", secondary: "secondary", ghost: "ghost" },
  },
  defaultVariants: { variant: "default" },
});
export function Button({
  asChild,
  variant,
  className,
  ...props
}: ComponentProps<"button"> &
  VariantProps<typeof variants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return (
    <Component className={cn(variants({ variant }), className)} {...props} />
  );
}
