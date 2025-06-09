import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store/store';
import Layout from './components/Layout';
import ListingsPage from './features/listings/ListingsPage';
import ListingDetail from './features/listings/ListingDetail';

function App() {
  useEffect(() => {
    console.log('App component mounted');
    return () => console.log('App component unmounted');
  }, []);

  console.log('App component rendering...');
  
  return (
    <div className="app">
      <Provider store={store}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ListingsPage />} />
              <Route path="listings" element={<ListingsPage />} />
              <Route path="listing/:id" element={<ListingDetail />} />
              <Route path="brands" element={<div>Brands Page</div>} />
              <Route path="about" element={<div>About Page</div>} />
              <Route path="contact" element={<div>Contact Page</div>} />
            </Route>
          </Routes>
        </BrowserRouter>
      </Provider>
    </div>
  );
}

export default App;
