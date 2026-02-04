import { Toaster as Sonner } from "sonner"

import { useTheme } from "@/components/theme-provider"

type ToasterProps = React.ComponentProps<typeof Sonner>

/**
 * Toaster component for displaying toast notifications.
 *
 * Supports success, error, warning, and info variants via sonner's built-in types.
 * Auto-dismisses after 5 seconds by default.
 *
 * Usage:
 *   import { toast } from "sonner"
 *
 *   toast.success("Service saved successfully")
 *   toast.error("Failed to save service")
 *   toast.warning("Service is currently muted")
 *   toast("Default notification")
 */
const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      duration={5000}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          success:
            "group-[.toaster]:border-status-healthy group-[.toaster]:text-status-healthy",
          error:
            "group-[.toaster]:border-status-error group-[.toaster]:text-status-error",
          warning:
            "group-[.toaster]:border-status-warning group-[.toaster]:text-status-warning",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
