import { cx } from "../utils/cx.js";

export const tabId = (prefix, value) => `${prefix}-tab-${value}`;
export const panelId = (prefix, value) => `${prefix}-panel-${value}`;

/** Abas com navegação por setas (Início/Fim também). O conteúdo fica a cargo de quem usa, em um role="tabpanel". */
export function Tabs({ tabs, value, onChange, label, prefix = "tabs", className }) {
  const move = (event, index) => {
    const keys = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const next = (keys[event.key] + tabs.length) % tabs.length;
    onChange(tabs[next].value);
    document.getElementById(tabId(prefix, tabs[next].value))?.focus();
  };
  return (
    <div className={cx("tabs", className)} role="tablist" aria-label={label}>
      {tabs.map((tab, index) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            id={tabId(prefix, tab.value)}
            aria-selected={selected}
            aria-controls={panelId(prefix, tab.value)}
            tabIndex={selected ? 0 : -1}
            className="tab"
            onClick={() => onChange(tab.value)}
            onKeyDown={(event) => move(event, index)}
          >
            {tab.label}
            {tab.count !== undefined && tab.count !== null && <span className="tab-count">{tab.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
