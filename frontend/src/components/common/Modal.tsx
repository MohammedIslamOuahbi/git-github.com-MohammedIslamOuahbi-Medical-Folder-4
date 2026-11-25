import type { ReactNode } from "react";
import { X } from "lucide-react";
import { translateUiText } from "@/utils/uiText";

export const Modal = ({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-md">
      <div className="w-full max-w-2xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl shadow-slate-950/20">

        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5 px-7">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-blue-700">
              {translateUiText("Modal Window")}
            </p>

            <h3 className="mt-1 text-2xl font-black tracking-tight text-slate-950">
              {translateUiText(title)}
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-500 transition-all duration-200 hover:bg-slate-100 hover:text-slate-950"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="max-h-[80vh] overflow-y-auto px-6 py-6 px-7 py-7">
          {children}
        </div>
      </div>
    </div>
  );
};
