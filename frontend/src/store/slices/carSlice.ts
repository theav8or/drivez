import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { api } from '../../api/client';
import type { CarListing, CarListingFilters } from '../../types/car';

interface ListingsResponse {
  items: CarListing[];
  total: number;
  page: number;
  limit: number;
}

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
  async (filters: CarListingFilters, { rejectWithValue }) => {
    try {
      const response = await api.get<ListingsResponse>('/car/listings', { 
        params: {
          ...filters,
          page: filters.page || 1,
          limit: filters.limit || 10,
        } 
      });
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to fetch listings');
    }
  }
);

export const triggerScrape = createAsyncThunk(
  'car/triggerScrape',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.post('/car/scrape');
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to trigger scrape');
    }
  }
);

export const carSlice = createSlice({
  name: 'car',
  initialState,
  reducers: {
    setFilters: (state, action: PayloadAction<Partial<CarListingFilters>>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    resetFilters: (state) => {
      state.filters = {};
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
        state.error = action.payload as string || 'Failed to fetch listings';
      })
      .addCase(triggerScrape.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(triggerScrape.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(triggerScrape.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string || 'Failed to trigger scrape';
      });
  },
});

export const { setFilters, resetFilters } = carSlice.actions;
export default carSlice.reducer;
