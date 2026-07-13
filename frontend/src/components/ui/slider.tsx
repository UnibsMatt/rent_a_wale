import * as React from "react";
import { cn } from "@/lib/utils";

export type SliderProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">;

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="range"
      className={cn(
        "h-2 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-[hsl(var(--primary))]",
        className,
      )}
      {...props}
    />
  ),
);
Slider.displayName = "Slider";

export { Slider };
