import React, { useEffect, useMemo } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store/store';
import { CacheProvider } from '@emotion/react';
import { I18nProvider, useI18n } from './i18n/I18nProvider';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import type { Direction } from '@mui/material/styles/types';
import { theme } from './theme/theme';
import CssBaseline from '@mui/material/CssBaseline';
import rtlPlugin from 'stylis-plugin-rtl';
import { prefixer } from 'stylis';
import createCache from '@emotion/cache';
import Layout from './components/Layout';
import ListingsPage from './features/listings/ListingsPage';
import ListingDetail from './features/listings/ListingDetail';

// Create RTL cache
const cacheRtl = createCache({
  key: 'muirtl',
  stylisPlugins: [prefixer, rtlPlugin],
  prepend: true,
});

// Create LTR cache
const cacheLtr = createCache({
  key: 'muiltl',
  prepend: true,
});

function AppContent() {
  const { language } = useI18n();
  
  // Determine direction based on language
  const direction = language === 'he' ? 'rtl' : 'ltr';
  
  // Create cache based on direction
  const cache = useMemo(() => 
    direction === 'rtl' ? cacheRtl : cacheLtr,
    [direction]
  );
  
  // Create theme with direction
  const themeWithDirection = useMemo(
    () => createTheme(theme, { direction }),
    [direction]
  );

  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={themeWithDirection}>
        <CssBaseline />
        <div className="app" dir={direction}>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<ListingsPage />} />
                <Route path="listings" element={<ListingsPage />} />
                <Route path="listings/:id" element={<ListingDetail />} />
                <Route path="brands" element={<div>Brands Page</div>} />
                <Route path="about" element={<div>About Page</div>} />
                <Route path="contact" element={<div>Contact Page</div>} />
              </Route>
            </Routes>
          </BrowserRouter>
        </div>
      </ThemeProvider>
    </CacheProvider>
  );
}

function App() {
  return (
    <Provider store={store}>
      <I18nProvider>
        <AppContent />
      </I18nProvider>
    </Provider>
  );
}

export default App;
