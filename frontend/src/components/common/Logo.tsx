import { useId } from "react";
import { cn } from "@/lib/utils";

interface LogoProps {
  /**
   * Layout variant:
   * - "horizontal": icon on left, "RehabTwin" text on right (standard for headers/navbars)
   * - "stacked": icon on top, "RehabTwin" text centered below (matches the original logo asset)
   * - "icon": icon mark only
   */
  variant?: "horizontal" | "stacked" | "icon";
  /**
   * Size presets
   */
  size?: "sm" | "md" | "lg" | "xl";
  /**
   * Inverted mode: changes dark navy elements to clean white for dark backgrounds (e.g. sidebar)
   */
  inverted?: boolean;
  /**
   * Additional container class names
   */
  className?: string;
  /**
   * Subtitle text (optional, e.g. "Therapist Dashboard" or "Patient Portal")
   */
  subtitle?: string;
}

export function Logo({
  variant = "horizontal",
  size = "md",
  inverted = false,
  className,
  subtitle,
}: LogoProps) {
  const uniqueId = useId();
  const roofGradId = `roof-grad-${uniqueId}`;
  const circuitGradId = `circuit-grad-${uniqueId}`;

  // Primary dark color: either dark slate (#1E293B) or white (#FFFFFF) when inverted
  const darkColor = inverted ? "#FFFFFF" : "currentColor";
  const darkStroke = inverted ? "#FFFFFF" : "#1E293B";
  const greenColor = "#10B981"; // Emerald green
  const greenDark = "#059669";

  // Size dimensions for icon
  const iconSizes = {
    sm: "size-7",
    md: "size-9",
    lg: "size-12",
    xl: "size-16",
  };

  const textSizes = {
    sm: "text-base",
    md: "text-lg",
    lg: "text-2xl",
    xl: "text-3xl",
  };

  const IconSVG = (
    <svg
      viewBox="0 0 140 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0", iconSizes[size])}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={roofGradId} x1="15%" y1="60%" x2="85%" y2="60%">
          <stop offset="0%" stopColor={inverted ? "#FFFFFF" : "#1E293B"} />
          <stop offset="50%" stopColor="#0D9488" />
          <stop offset="100%" stopColor={greenColor} />
        </linearGradient>
        <linearGradient id={circuitGradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={greenDark} />
          <stop offset="100%" stopColor={greenColor} />
        </linearGradient>
      </defs>

      {/* House Roof & Left Wall (Navy/Dark Slate or White) */}
      <path
        d="M 32 108 L 32 58 L 22 64 L 68 18"
        stroke={darkStroke}
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Right Roof Slope (Teal-Emerald Gradient) */}
      <path
        d="M 68 18 L 118 62 L 108 62"
        stroke={`url(#${roofGradId})`}
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Bottom-left foundation corner */}
      <path
        d="M 32 104 L 52 104"
        stroke={darkStroke}
        strokeWidth="9"
        strokeLinecap="round"
      />

      {/* Human Figure (Patient raising arm in recovery) */}
      <circle cx="60" cy="38" r="8" fill={darkStroke} />
      <path
        d="M 36 94 C 36 72 44 60 56 54 C 62 51 72 40 82 34 C 80 44 70 58 64 66 C 58 74 54 84 52 94 Z"
        fill={darkStroke}
      />

      {/* Digital Circuit / Twin Telemetry (Emerald) */}
      {/* Top Trace */}
      <path
        d="M 72 58 L 98 58"
        stroke={`url(#${circuitGradId})`}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="98" cy="58" r="4.5" fill={greenColor} />

      {/* Middle Trace */}
      <path
        d="M 70 74 L 110 74"
        stroke={`url(#${circuitGradId})`}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="110" cy="74" r="4.5" fill={greenColor} />

      {/* Bottom Trace */}
      <path
        d="M 70 90 L 96 90"
        stroke={`url(#${circuitGradId})`}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="96" cy="90" r="4.5" fill={greenColor} />

      {/* Bottom-Right Foundation Line */}
      <path
        d="M 70 104 L 102 104"
        stroke={greenColor}
        strokeWidth="9"
        strokeLinecap="round"
      />

      {/* Vertical Bus Connecting Traces */}
      <path
        d="M 70 58 L 70 104"
        stroke={greenColor}
        strokeWidth="6"
        strokeLinecap="round"
      />
    </svg>
  );

  if (variant === "icon") {
    return (
      <div className={cn("inline-flex items-center justify-center", className)}>
        {IconSVG}
      </div>
    );
  }

  if (variant === "stacked") {
    return (
      <div className={cn("inline-flex flex-col items-center text-center gap-2", className)}>
        {IconSVG}
        <div>
          <span
            className={cn(
              "font-extrabold tracking-tight select-none",
              textSizes[size],
              inverted ? "text-white" : "text-slate-900 dark:text-white"
            )}
          >
            Rehab<span className="text-emerald-500">Twin</span>
          </span>
          {subtitle && (
            <p className={cn("text-xs font-medium", inverted ? "text-slate-400" : "text-muted-foreground")}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Horizontal variant (default)
  return (
    <div className={cn("inline-flex items-center gap-3", className)}>
      {IconSVG}
      <div className="flex flex-col leading-tight">
        <span
          className={cn(
            "font-extrabold tracking-tight select-none",
            textSizes[size],
            inverted ? "text-white" : "text-slate-900 dark:text-white"
          )}
        >
          Rehab<span className="text-emerald-500">Twin</span>
        </span>
        {subtitle && (
          <span className={cn("text-xs font-medium", inverted ? "text-slate-400" : "text-muted-foreground")}>
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
