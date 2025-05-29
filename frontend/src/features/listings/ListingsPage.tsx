import React, { useEffect, useCallback } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../store';
import type { RootState } from '../../store';
import {
  Box,
  Button,
  TextField,
  Card,
  CardContent,
  CardMedia,
  CircularProgress,
  Alert,
  AlertTitle,
  IconButton,
  Tooltip,
  Typography,
  Pagination,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { 
  fetchListings, 
  setFilters, 
  resetFilters, 
  triggerScrape,
} from '../../store/slices/carSlice';
import type { CarListing, CarListingFilters } from '../../types/car';

const ITEMS_PER_PAGE = 10;

const ListingsPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { listings = [], loading, error, filters = {}, total = 0 } = useAppSelector(
    (state: RootState) => state.car
  );
  
  const page = filters?.page || 1;
  const totalPages = Math.ceil(total / ITEMS_PER_PAGE) || 1;

  const fetchData = useCallback(() => {
    dispatch(fetchListings({ 
      ...filters, 
      page,
      limit: ITEMS_PER_PAGE 
    }));
  }, [dispatch, filters, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePageChange = (_: React.ChangeEvent<unknown>, value: number) => {
    dispatch(setFilters({ ...filters, page: value }));
  };

  const handleFilterChange = (field: keyof CarListingFilters, value: any) => {
    dispatch(setFilters({ ...filters, [field]: value, page: 1 }));
  };

  const handleResetFilters = () => {
    dispatch(resetFilters());
  };

  const handleRefresh = () => {
    fetchData();
  };

  const handleTriggerScrape = async () => {
    try {
      await dispatch(triggerScrape()).unwrap();
      fetchData();
    } catch (err) {
      // Error is handled by the slice
    }
  };

  if (loading && !listings.length) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" component="h1" sx={{ mb: 0, mr: 2 }}>
              Car Listings
            </Typography>
            <Tooltip title="Refresh data">
              <span>
                <IconButton 
                  onClick={handleRefresh}
                  disabled={loading}
                  size="small"
                  sx={{ ml: 1 }}
                >
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>Error</AlertTitle>
              {error}
            </Alert>
          )}
          
          <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            <TextField
              label="Brand"
              value={filters.brand || ''}
              onChange={(e) => handleFilterChange('brand', e.target.value)}
              sx={{ width: '200px' }}
              size="small"
            />
            <TextField
              label="Model"
              value={filters.model || ''}
              onChange={(e) => handleFilterChange('model', e.target.value)}
              sx={{ width: '200px' }}
              size="small"
            />
            <TextField
              label="Min Price"
              type="number"
              value={filters.minPrice || ''}
              onChange={(e) => handleFilterChange('minPrice', Number(e.target.value))}
              sx={{ width: '150px' }}
              size="small"
            />
            <TextField
              label="Max Price"
              type="number"
              value={filters.maxPrice || ''}
              onChange={(e) => handleFilterChange('maxPrice', Number(e.target.value))}
              sx={{ width: '150px' }}
              size="small"
            />
            <TextField
              label="Year From"
              type="number"
              value={filters.yearFrom || ''}
              onChange={(e) => handleFilterChange('yearFrom', Number(e.target.value))}
              sx={{ width: '150px' }}
              size="small"
            />
            <TextField
              label="Year To"
              type="number"
              value={filters.yearTo || ''}
              onChange={(e) => handleFilterChange('yearTo', Number(e.target.value))}
              sx={{ width: '150px' }}
              size="small"
            />
          </Box>
          
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 2 }}>
            <Button 
              variant="outlined" 
              onClick={handleResetFilters}
              disabled={loading}
            >
              Reset Filters
            </Button>
            <Button 
              variant="contained" 
              color="primary" 
              onClick={handleTriggerScrape}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} /> : null}
            >
              Scrape New Data
            </Button>
          </Box>
        </CardContent>
      </Card>

      {listings.length > 0 ? (
        <Box 
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(3, 1fr)',
              lg: 'repeat(4, 1fr)'
            },
            gap: 3,
            width: '100%'
          }}
        >
          {listings.map((listing: CarListing) => (
            <Box 
              key={listing.id}
              sx={{ 
                display: 'flex',
                width: '100%'
              }}
            >
              <Card
                key={listing.id}
                component={RouterLink}
                to={`/listing/${listing.id}`}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  textDecoration: 'none',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 6,
                  },
                }}
              >
                {listing.image && (
                  <CardMedia
                    component="img"
                    height="140"
                    image={listing.image}
                    alt={listing.title}
                  />
                )}
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography gutterBottom variant="h6" component="div">
                    {listing.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    שנת ייצור: {listing.year}
                  </Typography>
                  <Typography variant="h6" color="primary" sx={{ mt: 1 }}>
                    {new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS' }).format(listing.price)}
                  </Typography>
                  {listing.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ 
                      mt: 1, 
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis' 
                    }}>
                      {listing.description}
                    </Typography>
                  )}
                  {listing.mileage && (
                    <Typography variant="body2" color="text.secondary">
                      קילומטרז: {listing.mileage.toLocaleString('he-IL')} ק״מ
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
      ) : (
        <Box textAlign="center" py={4}>
          <Typography variant="h6" color="textSecondary">
            No listings found. Try adjusting your filters or scrape for new data.
          </Typography>
        </Box>
      )}

      {totalPages > 1 && (
        <Box display="flex" justifyContent="center" mt={4} mb={2}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={handlePageChange}
            color="primary"
            showFirstButton
            showLastButton
          />
        </Box>
      )}
    </Box>
  );
};

export default ListingsPage;
