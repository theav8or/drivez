import React from 'react';
import { useAppDispatch, useAppSelector } from '@/store';
import type { RootState } from '@/store';
import {
  Box,
  Button,
  TextField,
  FormControl,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Pagination,
  Typography,
} from '@mui/material';
import { fetchListings, setFilters } from '../../store/slices/carSlice';
import type { CarListing, CarListingFilters } from '../../types/car';

const ListingsPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { listings, loading, error, filters, total } = useAppSelector((state: RootState) => state.car);

  const handleFilterChange = (field: keyof CarListingFilters, value: any) => {
    dispatch(setFilters({ ...filters, [field]: value }));
    dispatch(fetchListings(filters));
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 4 }}>
        <TextField
          label="Brand"
          value={filters.brand || ''}
          onChange={(e) => handleFilterChange('brand', e.target.value)}
          sx={{ width: '200px' }}
        />
        <TextField
          label="Model"
          value={filters.model || ''}
          onChange={(e) => handleFilterChange('model', e.target.value)}
          sx={{ width: '200px' }}
        />
        <TextField
          label="Min Price"
          type="number"
          value={filters.minPrice || ''}
          onChange={(e) => handleFilterChange('minPrice', Number(e.target.value))}
          sx={{ width: '150px' }}
        />
        <TextField
          label="Max Price"
          type="number"
          value={filters.maxPrice || ''}
          onChange={(e) => handleFilterChange('maxPrice', Number(e.target.value))}
          sx={{ width: '150px' }}
        />
        <Button
          variant="outlined"
          onClick={() => {
            dispatch(setFilters({}));
            dispatch(fetchListings({}));
          }}
          sx={{ width: '150px' }}
        >
          Clear Filters
        </Button>
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Price</TableCell>
              <TableCell>Year</TableCell>
              <TableCell>Mileage</TableCell>
              <TableCell>Location</TableCell>
              <TableCell>Source</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {listings.map((listing: CarListing) => (
              <TableRow key={listing.id}>
                <TableCell>{listing.title}</TableCell>
                <TableCell>{listing.price.toLocaleString()}</TableCell>
                <TableCell>{listing.year}</TableCell>
                <TableCell>{listing.mileage.toLocaleString()}</TableCell>
                <TableCell>{listing.location}</TableCell>
                <TableCell>{listing.source}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
        <Pagination
          count={Math.ceil(total / (filters.limit || 10))}
          page={filters.page || 1}
          onChange={(_, page) => handleFilterChange('page', page)}
        />
      </Box>
    </Box>
  );
};

export default ListingsPage;
