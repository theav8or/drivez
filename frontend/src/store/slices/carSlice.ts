import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { api } from '../../api/client';
import type { CarListing, CarListingFilters } from '../../types/car';

export interface CarState {
  listings: CarListing[];
  loading: boolean;
  error: string | null;
  filters: CarListingFilters;
  total: number;
}

const initialState: CarState = {
  listings: [],
  loading: false,
  error: null,
  filters: {},
  total: 0,
};

export const fetchListings = createAsyncThunk(
  'car/fetchListings',
  async (filters: CarListingFilters) => {
    const response = await api.get('/listings', { params: filters });
    return response.data;
  }
);

export const carSlice = createSlice({
  name: 'car',
  initialState,
  reducers: {
    setFilters: (state, action) => {
      state.filters = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchListings.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchListings.fulfilled, (state, action) => {
        state.loading = false;
        state.listings = action.payload.items;
        state.total = action.payload.total;
      })
      .addCase(fetchListings.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch listings';
      });
  },
});

export const { setFilters } = carSlice.actions;
export default carSlice.reducer;
