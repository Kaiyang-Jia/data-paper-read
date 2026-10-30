export function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    user: "M20 21v-2a7 7 0 0 0-14 0v2M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
    sliders: "M4 7h7m4 0h5M4 17h3m4 0h9M11 4v6M7 14v6",
    bookmark: "M6 3h12v18l-6-4-6 4V3",
    plus: "M12 5v14M5 12h14",
    list: "M4 5h16M4 9h11M4 15h16M4 19h11",
    compact: "M4 5h16M4 10h16M4 15h16M4 20h16",
    search: "m21 21-4.5-4.5M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0",
    book: "M4 3h13a3 3 0 0 1 3 3v15H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3M3 17h17M8 7h7M8 11h5",
    spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3",
    folder: "M3 7V4h7l2 3h9v13H3V7",
    arrow: "M4 12h16m-6-6 6 6-6 6",
    check: "m5 12 4 4L19 6",
    link: "M14 3h7v7M21 3 11 13M10 5H3v16h16v-7",
    info: "M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.book} />
    </svg>
  );
}
