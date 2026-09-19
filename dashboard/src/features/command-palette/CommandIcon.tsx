import type { CommandIconName } from './commandRegistry';

function assertNever(value: never): never {
  return value;
}

function iconPath(icon: CommandIconName) {
  switch (icon) {
    case 'search':
      return <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>;
    case 'note':
      return <><path d="M6 3h9l3 3v15H6z" /><path d="M9 10h6M9 14h6M9 18h4" /></>;
    case 'chat':
      return <path d="M4 5h16v11H9l-5 4z" />;
    case 'automation':
      return <><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /><circle cx="12" cy="12" r="5" /></>;
    case 'settings':
      return <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></>;
    case 'sync':
      return <><path d="M20 7h-5V2" /><path d="M19 7a8 8 0 1 0 1 8" /></>;
    case 'test':
      return <><path d="M9 3h6M10 3v5l-5 10a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3L14 8V3" /><path d="M8 15h8" /></>;
    case 'plugin':
      return <path d="M8 3v5H3v8h5v5h8v-5h5V8h-5V3z" />;
    case 'warning':
      return <><path d="M12 3 2 21h20z" /><path d="M12 9v5M12 18h.01" /></>;
    default:
      return assertNever(icon);
  }
}

export function CommandIcon({ icon }: Readonly<{ icon: CommandIconName }>) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
      {iconPath(icon)}
    </svg>
  );
}
