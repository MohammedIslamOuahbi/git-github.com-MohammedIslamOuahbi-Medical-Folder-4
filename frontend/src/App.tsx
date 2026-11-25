import { DesktopOnlyGuard } from "@/components/system/DesktopOnlyGuard";
import { AppRoutes } from "@/routes/AppRoutes";

export default function App() {
  return (
    <DesktopOnlyGuard>
      <AppRoutes />
    </DesktopOnlyGuard>
  );
}
