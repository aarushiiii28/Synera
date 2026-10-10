import React from 'react';

export function Stars() {
  const [stars, setStars] = React.useState<{x: number, y: number, size: number, opacity: number}[]>([]);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStars(Array.from({ length: 150 }).map(() => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 1.5 + 0.5,
      opacity: Math.random() * 0.5 + 0.1
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
