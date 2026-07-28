export const SquareSnake = () => {
  return (
    <div
      className="loader-surface grid h-10 w-10 grid-cols-3 gap-1"
      aria-hidden="true"
    >
      {[
        [0, 0],
        [1, 0],
        [2, 0],
        [0, 1],
        [1, 1],
        [2, 1],
        [0, 2],
        [1, 2],
        [2, 2],
      ].map(([x, y], i) => (
        <div
          key={i}
          className="animate-square-snake h-full w-full rounded-sm bg-zinc-800 dark:bg-white"
          style={{ animationDelay: `${(x + y) * 0.15}s` }}
        />
      ))}
    </div>
  );
};
