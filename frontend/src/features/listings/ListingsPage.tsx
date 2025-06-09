import React, { useEffect, useCallback, useMemo, useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../store';
import type { RootState } from '../../store';
import { useI18n } from '../../i18n/I18nProvider';
import { scraperApi, type ScrapeTask } from '../../api/scraper';
import {
  Box,
  Button,
  TextField,
  Card,
  CardContent,
  CardMedia,
  CardActionArea,
  CircularProgress,
  Alert,
  AlertTitle,
  IconButton,
  Tooltip,
  Typography,
  Pagination,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
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
  const { t } = useI18n();
  
  const [scrapeDialogOpen, setScrapeDialogOpen] = useState(false);
  const [scrapeProgress, setScrapeProgress] = useState(0);
  const [scrapeStatus, setScrapeStatus] = useState<ScrapeTask | null>(null);
  const [scrapeError, setScrapeError] = useState<string | null>(null);
  const [maxPages, setMaxPages] = useState(5);
  const [scrapePolling, setScrapePolling] = useState<ReturnType<typeof setInterval> | null>(null);
  
  const page = filters?.page || 1;
  const totalPages = Math.ceil(total / ITEMS_PER_PAGE) || 1;
  
  // Handle filter changes
  const onFilterChange = useCallback((field: keyof CarListingFilters, value: any) => {
    dispatch(setFilters({ ...filters, [field]: value, page: 1 }));
  }, [dispatch, filters]);

  // Create individual input components to maintain focus
  const InputField = React.memo(({ 
    field, 
    label, 
    type = 'text', 
    value = '',
    disabled = false,
    sx = {}
  }: {
    field: keyof CarListingFilters;
    label: string;
    type?: string;
    value?: any;
    disabled?: boolean;
    sx?: object;
  }) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = type === 'number' 
        ? (e.target as HTMLInputElement).valueAsNumber || '' 
        : e.target.value;
      onFilterChange(field, newValue);
    };

    return (
      <TextField
        key={`${field}-input`}
        label={label}
        type={type}
        value={value || ''}
        onChange={handleChange}
        disabled={disabled}
        size="small"
        sx={{
          minWidth: 120,
          '&:not(:last-child)': { mr: 1 },
          ...sx
        }}
      />
    );
  });

  // Memoize the filter inputs to prevent re-renders
  const filterInputs = useMemo(() => (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
      <InputField 
        field="brand" 
        label={t('brand')} 
        value={filters.brand}
        disabled={loading}
      />
      <InputField 
        field="model" 
        label={t('model')} 
        value={filters.model}
        disabled={loading}
      />
      <InputField 
        field="minPrice" 
        label={t('minPrice')} 
        type="number"
        value={filters.minPrice}
        disabled={loading}
        sx={{ maxWidth: 140 }}
      />
      <InputField 
        field="maxPrice" 
        label={t('maxPrice')} 
        type="number"
        value={filters.maxPrice}
        disabled={loading}
        sx={{ maxWidth: 140 }}
      />
      <InputField 
        field="yearFrom" 
        label={t('minYear')} 
        type="number"
        value={filters.yearFrom}
        disabled={loading}
        sx={{ maxWidth: 120 }}
      />
      <InputField 
        field="yearTo" 
        label={t('maxYear')} 
        type="number"
        value={filters.yearTo}
        disabled={loading}
        sx={{ maxWidth: 120 }}
      />
    </Box>
  ), [filters, loading, t, onFilterChange]);

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

  // Poll for scrape status
  const pollScrapeStatus = useCallback(async (taskId: string) => {
    if (scrapePolling) {
      clearInterval(scrapePolling);
    }
    
    const poll = async () => {
      try {
        const status = await scraperApi.getStatus(taskId);
        setScrapeStatus(status);
        
        // Update progress
        if (status.details?.progress) {
          setScrapeProgress(status.details.progress);
        }
        
        // If task is done, stop polling
        if (['completed', 'error', 'not_found'].includes(status.status)) {
          if (scrapePolling) {
            clearInterval(scrapePolling);
            setScrapePolling(null);
          }
          
          // Refresh listings if successful
          if (status.status === 'completed' && status.result) {
            dispatch(fetchListings(filters));
          }
        }
      } catch (err) {
        console.error('Error polling scrape status:', err);
        setScrapeError('Failed to check scrape status');
        if (scrapePolling) {
          clearInterval(scrapePolling);
          setScrapePolling(null);
        }
      }
    };
    
    // Start polling every 2 seconds
    const intervalId = setInterval(poll, 2000);
    setScrapePolling(intervalId);
    
    // Initial poll
    poll();
    
    return () => {
      if (scrapePolling) {
        clearInterval(scrapePolling);
      }
    };
  }, [dispatch, filters, scrapePolling]);
  
  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (scrapePolling) {
        clearInterval(scrapePolling);
      }
    };
  }, [scrapePolling]);
  
  const handleTriggerScrape = async () => {
    try {
      setScrapeDialogOpen(true);
      setScrapeProgress(0);
      setScrapeStatus(null);
      setScrapeError(null);
      
      // Start the scrape
      const result = await scraperApi.startScraping(maxPages);
      setScrapeStatus(result);
      
      // Start polling for status
      if (result.task_id) {
        pollScrapeStatus(result.task_id);
      }
      
    } catch (err) {
      setScrapeError(err instanceof Error ? err.message : 'Failed to start scraping');
      setScrapeDialogOpen(false);
    }
  };
  
  const handleMaxPagesChange = (event: SelectChangeEvent<number>) => {
    setMaxPages(Number(event.target.value));
  };

  const handleCloseScrapeDialog = () => {
    setScrapeDialogOpen(false);
    // Don't reset status if scraping is in progress
    if (!scrapeStatus || ['completed', 'error', 'not_found'].includes(scrapeStatus.status)) {
      setScrapeStatus(null);
      setScrapeError(null);
      setScrapeProgress(0);
    }
  };

  return (
    <Box sx={{ p: 3, direction: 'rtl' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" component="h2">
          {t('listings')} ({total})
        </Typography>
        <Box>
          <Tooltip title="Scrape new listings from Yad2">
            <span>
              <Button
                variant="contained"
                color="primary"
                onClick={handleTriggerScrape}
                disabled={loading || (scrapeStatus?.status === 'running')}
                startIcon={<CloudDownloadIcon />}
                sx={{ mr: 1 }}
              >
                {t('scrapeListings')}
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="Refresh current listings">
            <span>
              <Button
                variant="outlined"
                onClick={handleRefresh}
                disabled={loading}
                startIcon={<RefreshIcon />}
              >
                {t('refresh')}
              </Button>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {filterInputs}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 3, mb: 3 }}>
            {listings.map((listing) => (
              <Card key={listing.id} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardActionArea 
                  component={RouterLink} 
                  to={`/listings/${listing.id}`}
                  sx={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                >
                  {listing.thumbnail_url && (
                    <CardMedia
                      component="img"
                      height="140"
                      image={listing.thumbnail_url}
                      alt={listing.title}
                      sx={{ objectFit: 'cover' }}
                    />
                  )}
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography gutterBottom variant="h6" component="h3">
                      {listing.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {listing.year} • {listing.mileage?.toLocaleString()} km • {listing.fuel_type}
                    </Typography>
                    {listing.price && (
                      <Typography variant="h6" color="primary" fontWeight="bold">
                        {listing.price.toLocaleString()} ₪
                      </Typography>
                    )}
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Box>

          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
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
        </>
      )}

      {/* Scrape Dialog */}
      <Dialog open={scrapeDialogOpen} onClose={handleCloseScrapeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Scraping Listings from Yad2</DialogTitle>
        <DialogContent>
          {scrapeError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>Error</AlertTitle>
              {scrapeError}
            </Alert>
          )}
          
          {!scrapeStatus ? (
            <Box sx={{ mt: 2 }}>
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel id="max-pages-label">Max Pages to Scrape</InputLabel>
                <Select
                  labelId="max-pages-label"
                  id="max-pages"
                  value={maxPages}
                  label="Max Pages to Scrape"
                  onChange={handleMaxPagesChange}
                  disabled={loading}
                >
                  {[1, 2, 3, 5, 10, 20, 50].map(num => (
                    <MenuItem key={num} value={num}>
                      {num} {num === 1 ? 'page' : 'pages'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                This will scrape up to {maxPages} pages of listings from Yad2.
              </Typography>
              
              <Typography variant="body2" color="text.secondary">
                Note: Scraping may take a few minutes depending on the number of pages.
              </Typography>
            </Box>
          ) : (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Status: <strong>{scrapeStatus.status.toUpperCase()}</strong>
              </Typography>
              
              {scrapeStatus.details?.started_at && (
                <Typography variant="body2" color="text.secondary">
                  Started: {new Date(scrapeStatus.details.started_at).toLocaleString()}
                </Typography>
              )}
              
              {scrapeStatus.details?.max_pages && (
                <Typography variant="body2" color="text.secondary">
                  Pages to scrape: {scrapeStatus.details.max_pages}
                </Typography>
              )}
              
              {scrapeStatus.details?.message && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic' }}>
                  {scrapeStatus.details.message}
                </Typography>
              )}
              
              {scrapeStatus.result && (
                <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Results:
                  </Typography>
                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                    <Typography variant="body2">
                      Created: <strong>{scrapeStatus.result.created}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Updated: <strong>{scrapeStatus.result.updated}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Total: <strong>{scrapeStatus.result.total}</strong>
                    </Typography>
                  </Box>
                </Box>
              )}
              
              <Box sx={{ mt: 3, mb: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Progress
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {scrapeProgress}%
                  </Typography>
                </Box>
                <LinearProgress 
                  variant={scrapeStatus.status === 'running' ? 'buffer' : 'determinate'} 
                  value={scrapeProgress} 
                  valueBuffer={scrapeStatus.status === 'running' ? 100 : undefined}
                  sx={{ 
                    height: 10, 
                    borderRadius: 5,
                    '& .MuiLinearProgress-bar': {
                      borderRadius: 5,
                    }
                  }}
                />
              </Box>
              
              {scrapeStatus.status === 'completed' && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  Scraping completed successfully!
                </Alert>
              )}
              
              {scrapeStatus.status === 'error' && scrapeStatus.error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  <AlertTitle>Scraping Error</AlertTitle>
                  {scrapeStatus.error}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button 
            onClick={handleCloseScrapeDialog}
            disabled={scrapeStatus?.status === 'running'}
            variant="outlined"
            color="inherit"
          >
            {scrapeStatus?.status === 'completed' ? 'Done' : 'Cancel'}
          </Button>
          
          {scrapeStatus?.status === 'completed' && (
            <Button 
              onClick={handleRefresh}
              color="primary"
              variant="contained"
            >
              View Updated Listings
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ListingsPage;
