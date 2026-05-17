import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, className = "h-5 w-5", ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      {children}
    </svg>
  );
}

export function SparkIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 2.8 13.9 8l5.3 1.9-5.3 1.9L12 17.2l-1.9-5.4-5.3-1.9L10.1 8 12 2.8Z" />
      <path d="m18 15 .8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8L18 15Z" />
    </IconBase>
  );
}

export function BrainIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M9 4.5a3 3 0 0 0-3 3v.2a3.2 3.2 0 0 0-2 3 3.1 3.1 0 0 0 1.4 2.6 3.4 3.4 0 0 0 3.3 4.2H10V4.5H9Z" />
      <path d="M15 4.5a3 3 0 0 1 3 3v.2a3.2 3.2 0 0 1 2 3 3.1 3.1 0 0 1-1.4 2.6 3.4 3.4 0 0 1-3.3 4.2H14V4.5h1Z" />
      <path d="M10 8.5H8.8A2.8 2.8 0 0 0 6 11.3" />
      <path d="M14 8.5h1.2a2.8 2.8 0 0 1 2.8 2.8" />
    </IconBase>
  );
}

export function SendIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m4 12 15-7-4.2 14-3.3-5.6L4 12Z" />
      <path d="m11.5 13.4 3.3-8.4" />
    </IconBase>
  );
}

export function DatabaseIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <ellipse cx="12" cy="5.5" rx="7" ry="3" />
      <path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      <path d="M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </IconBase>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 7h16" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M6.5 7 7 20h10l.5-13" />
      <path d="M9 7V4h6v3" />
    </IconBase>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </IconBase>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </IconBase>
  );
}

export function XIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m6 6 12 12" />
      <path d="M18 6 6 18" />
    </IconBase>
  );
}

export function MessageIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v4A3.5 3.5 0 0 1 15.5 14H11l-4.5 4v-4A3.5 3.5 0 0 1 3 10.5v-4Z" />
    </IconBase>
  );
}

export function BotIcon(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 4V2" />
      <path d="M7.5 7h9A3.5 3.5 0 0 1 20 10.5v4A3.5 3.5 0 0 1 16.5 18h-9A3.5 3.5 0 0 1 4 14.5v-4A3.5 3.5 0 0 1 7.5 7Z" />
      <path d="M9 12h.01" />
      <path d="M15 12h.01" />
      <path d="M9.5 15h5" />
    </IconBase>
  );
}
