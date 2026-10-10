import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import './design/tokens.css';
import '@fontsource/sora/300.css';
import '@fontsource/sora/600.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '@fontsource/instrument-serif/400-italic.css';
import './index.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
