import React, { useEffect, useRef } from "react";
import { X } from "lucide-react";
export {api, setToken} from "./workbench-api.js";

export const cats = {
  system: "Sistem",
  subsystem: "Alt sistem",
  component: "Bileşen",
  external: "Dış sistem",
};
export const types = {
  data: "Veri",
  control: "Kontrol",
  power: "Güç",
  communication: "Haberleşme",
  mechanical: "Mekanik",
  thermal: "Termal",
  unknown: "Belirtilmemiş",
};
export const uid = (p) => p + "_" + crypto.randomUUID().slice(0, 8);
export function Button({ icon: Icon, children, className = "", ...props }) {
  return (
    <button type="button" className={"button " + className} {...props}>
      {Icon && <Icon size={16} />}
      <span>{children}</span>
    </button>
  );
}
export function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {React.cloneElement(children, {
        "aria-label": children.props["aria-label"] || label,
      })}
    </label>
  );
}
export function Drawer({ title, onClose, children }) {
  const ref = useRef();
  useEffect(() => {
    const prev = document.activeElement;
    ref.current.showModal();
    return () => {
      ref.current?.close();
      prev?.focus?.();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="workspace-drawer"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Pencereyi kapat"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function applyPreview(architecture, changes = []) {
  const a = structuredClone(architecture);
  for (const c of changes) {
    const field = c.kind === "component" ? "components" : "connections";
    const index = a[field].findIndex((o) => o.id === c.id);
    if (c.action === "remove") {
      if (index >= 0) a[field][index]._preview = "remove";
      if (c.kind === "component")
        a.connections
          .filter((e) => e.source === c.id || e.target === c.id)
          .forEach((e) => (e._preview = "remove"));
    } else {
      const item = {
        ...(index >= 0 ? a[field][index] : { evidence: [] }),
        ...c.value,
        id: c.id,
        _preview: c.action,
      };
      if (index >= 0) a[field][index] = item;
      else a[field].push(item);
    }
  }
  return a;
}
