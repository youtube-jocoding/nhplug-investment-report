import { useEffect, useRef } from "react";
import { X } from "lucide-react";
export function Modal({ title, children, onClose, wide = false }) {
  const ref = useRef();
  useEffect(() => {
    const before = document.activeElement;
    ref.current.showModal();
    return () => {
      before?.focus();
    };
  }, []);
  return (
    <dialog ref={ref} className={wide ? "wide" : ""} onCancel={onClose}>
      <div className="dialog-head">
        <h2>{title}</h2>
        <button className="icon" aria-label="닫기" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
