import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store/store';
import Layout from './components/Layout';
import ListingsPage from './features/listings/ListingsPage';

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
            <Route path="/" element={
              <div>
                <div>Rendering Layout...</div>
                <Layout />
              </div>
            }>
              <Route index element={
                <div>
                  <div>Rendering ListingsPage...</div>
                  <ListingsPage />
                </div>
              } />
            </Route>
          </Routes>
        </BrowserRouter>
      </Provider>
    </div>
  );
}

export default App;
