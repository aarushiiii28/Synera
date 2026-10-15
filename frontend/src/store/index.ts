import { create } from 'zustand';

interface UI {
  tourStep: number | null;
  startTour: () => void;
  goTour: (n: number | null) => void;
  selectedPair: [string, string] | null;
  selectPair: (p: [string, string] | null) => void;
  railOpen: boolean;
  setRailOpen: (v: boolean) => void;
}

export const useUI = create<UI>((set) => ({
  tourStep: null,
  startTour: () => set({ tourStep: 0 }),
  goTour: (n) => set({ tourStep: n }),
  selectedPair: null,
  selectPair: (p) => set({ selectedPair: p }),
  railOpen: false,
  setRailOpen: (v) => set({ railOpen: v }),
}));
