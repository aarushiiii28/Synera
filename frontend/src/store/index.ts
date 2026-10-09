import { create } from 'zustand';

interface AppState {
  selectedDataset: string | null;
  setSelectedDataset: (id: string | null) => void;
  selectedPair: [string, string] | null;
  setSelectedPair: (pair: [string, string] | null) => void;
}

export const useStore = create<AppState>((set) => ({
  selectedDataset: 'env_panel', // default
  setSelectedDataset: (id) => set({ selectedDataset: id }),
  selectedPair: null,
  setSelectedPair: (pair) => set({ selectedPair: pair }),
}));
