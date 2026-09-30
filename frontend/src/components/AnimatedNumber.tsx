import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { motion as tokens } from "../theme/tokens";

interface AnimatedNumberProps {
  value: number;
  format: (value: number) => string;
  /** Durée en secondes (< 0,9 s pour un compteur de KPI). */
  duration?: number;
}

/**
 * Compteur : anime de la valeur précédente vers la nouvelle (au chargement et quand un filtre
 * change), pour signaler que le chiffre a été recalculé. Aucun mouvement si l'utilisateur a
 * demandé à réduire les animations.
 */
export function AnimatedNumber({ value, format, duration = tokens.duration.counter }: AnimatedNumberProps) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);
  const previous = useRef(0);

  useEffect(() => {
    if (reduce) {
      previous.current = value;
      return;
    }
    const controls = animate(previous.current, value, {
      duration: Math.min(duration, 0.9),
      ease: tokens.ease.standard,
      onUpdate: setDisplay,
    });
    previous.current = value;
    return () => {
      controls.stop();
    };
  }, [value, duration, reduce]);

  // Mouvement réduit : valeur finale affichée directement, sans état intermédiaire.
  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{format(reduce ? value : display)}</span>;
}
