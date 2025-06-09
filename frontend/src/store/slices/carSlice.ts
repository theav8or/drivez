import { createSlice, createAsyncThunk, createSelector } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { api } from '../../api/client';
import type { CarListing, CarListingFilters } from '../../types/car';

interface ListingsResponse extends Array<CarListing> {
  // The API returns an array of CarListing directly
}

export interface CarState {
  listings: CarListing[];
  currentListing: CarListing | null;
  loading: boolean;
  error: string | null;
  filters: CarListingFilters;
  total: number;
}

const initialState: CarState = {
  listings: [],
  currentListing: null,
  loading: false,
  error: null,
  filters: {},
  total: 0,
};

export const fetchListings = createAsyncThunk(
  'car/fetchListings',
  async (filters: CarListingFilters, { rejectWithValue }) => {
    try {
      const response = await api.get<CarListing[]>('/listings', { 
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

export const fetchListingById = createAsyncThunk(
  'car/fetchListingById',
  async (id: number, { rejectWithValue }) => {
    try {
      const response = await api.get<CarListing>(`/listings/${id}`);
      if (!response.data) {
        throw new Error('Listing not found');
      }
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message || 'Failed to fetch listing');
    }
  }
);

export const triggerScrape = createAsyncThunk(
  'car/triggerScrape',
  async (maxPages: number = 5, { rejectWithValue }) => {
    try {
      const response = await api.post('/scrape/yad2', { max_pages: maxPages });
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to trigger scrape');
    }
  }
);

export const checkScrapeStatus = createAsyncThunk(
  'car/checkScrapeStatus',
  async (taskId: string, { rejectWithValue }) => {
    try {
      const response = await api.get(`/scrape/status/${taskId}`);
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to check scrape status');
    }
  }
);

export const carSlice = createSlice({
  name: 'car',
  initialState,
  reducers: {
    setFilters(state, action: PayloadAction<Partial<CarListingFilters>>) {
      state.filters = { ...state.filters, ...action.payload };
    },
    resetFilters(state) {
      state.filters = {};
    },
    resetCurrentListing(state) {
      state.currentListing = null;
      state.loading = false;
      state.error = null;
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
        state.listings = action.payload;
        state.error = null;
      })
      .addCase(fetchListings.rejected, (state, action) => {
        state.loading = false;
      })
      // Handle scrape status checks
      .addCase(checkScrapeStatus.fulfilled, (state, action) => {
        // Update UI based on scrape status if needed
        if (action.payload.status === 'completed' && action.payload.result) {
          // Optionally refresh listings after successful scrape
          state.loading = false;
        } else if (action.payload.status === 'error') {
          state.error = action.payload.error || 'Scraping failed';
          state.loading = false;
        }
        state.error = action.payload as string;
      })
      .addCase(fetchListingById.pending, (state) => {
        state.loading = true;
        state.error = null;
        state.currentListing = null;
      })
      .addCase(fetchListingById.fulfilled, (state, action) => {
        state.loading = false;
        state.currentListing = action.payload;
        state.error = null;
      })
      .addCase(fetchListingById.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
        state.currentListing = null;
      })
      // Handle scrape triggers - single set of handlers
      .addCase(triggerScrape.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(triggerScrape.fulfilled, (state, action) => {
        state.loading = false;
        state.error = null;
      })
      .addCase(triggerScrape.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string || 'Failed to trigger scrape';
      });
  },
});

// Selectors
export const selectCarState = (state: { car: CarState }) => state.car;

export const selectCurrentListing = createSelector(
  [selectCarState],
  (car) => car.currentListing
);

export const selectCarLoading = createSelector(
  [selectCarState],
  (car) => car.loading
);

export const selectCarError = createSelector(
  [selectCarState],
  (car) => car.error
);

export const { setFilters, resetFilters, resetCurrentListing } = carSlice.actions;
export default carSlice.reducer;
