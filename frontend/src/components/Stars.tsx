import React from 'react';

export function Stars() {
  const [stars, setStars] = React.useState<{x: number, y: number, size: number, opacity: number}[]>([]);

  React.useEffect(() => {
    let seed = 1337;
    const prng = () => {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      return seed / 4294967296;
    };
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStars(Array.from({ length: 150 }).map(() => ({
      x: prng() * 100,
      y: prng() * 100,
      size: prng() * 1.5 + 0.5,
      opacity: prng() * 0.5 + 0.1
    })));
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none z-0" aria-hidden>
      {stars.map((star, i) => (
        <div 
          key={i}
          className="absolute rounded-full bg-white"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            opacity: star.opacity
          }}
        />
      ))}
    </div>
  );
}
