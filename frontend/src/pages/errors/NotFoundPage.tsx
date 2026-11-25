import { Link } from "react-router-dom";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

export const NotFoundPage = () => (
  <div className="flex min-h-screen items-center justify-center px-4">
    <Card className="max-w-lg text-center">
      <p className="text-xs uppercase tracking-[0.3em] text-brand-700">404 Error</p>
      <h1 className="mt-4 text-4xl font-semibold text-ink-900">Page not found</h1>
      <p className="mt-4 text-sm text-ink-600">
        The page you requested could not be located. Return to your role dashboard to continue.
      </p>
      <div className="mt-8">
        <Link to="/dashboard">
          <Button>Return to dashboard</Button>
        </Link>
      </div>
    </Card>
  </div>
);
