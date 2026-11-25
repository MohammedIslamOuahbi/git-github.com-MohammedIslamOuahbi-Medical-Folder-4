import { Button } from "@/components/common/Button";
import { Modal } from "@/components/common/Modal";

export const ConfirmModal = ({
  open,
  title,
  description,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => void;
  onClose: () => void;
}) => (
  <Modal open={open} title={title} onClose={onClose}>
    <p className="text-sm text-ink-600">{description}</p>
    <div className="mt-6 flex justify-end gap-3">
      <Button variant="secondary" onClick={onClose}>
        Cancel
      </Button>
      <Button variant="danger" onClick={onConfirm}>
        Confirm
      </Button>
    </div>
  </Modal>
);
