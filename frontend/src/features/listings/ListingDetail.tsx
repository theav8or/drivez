import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../store';
import { useI18n } from '../../i18n/I18nProvider';
import { 
  fetchListingById, 
  selectCurrentListing, 
  selectCarLoading, 
  selectCarError,
  resetCurrentListing 
} from '../../store/slices/carSlice';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Button,
  CircularProgress,
  Alert,
  AlertTitle,
  Container,
  Grid,
  CardMedia,
  Chip
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const ListingDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  
  const currentListing = useAppSelector(selectCurrentListing);
  const loading = useAppSelector(selectCarLoading);
  const error = useAppSelector(selectCarError);
  const { t } = useI18n();

  useEffect(() => {
    if (id) {
      dispatch(fetchListingById(parseInt(id)));
    }
    
    // Cleanup function to reset the current listing when component unmounts
    return () => {
      dispatch(resetCurrentListing());
    };
  }, [dispatch, id]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2, textAlign: 'right' }}>
        <AlertTitle>{t('error')}</AlertTitle>
        {error}
      </Alert>
    );
  }

  if (!currentListing) {
    return (
      <Alert severity="warning" sx={{ m: 2, textAlign: 'right' }}>
        <AlertTitle>{t('listingNotFound')}</AlertTitle>
        {t('listingNotFoundMessage')}
      </Alert>
    );
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderSpecification = (label: string, value: React.ReactNode, key?: string) => {
    // Handle case where value is an object
    const displayValue = value && typeof value === 'object' && !React.isValidElement(value)
      ? JSON.stringify(value)
      : value;
      
    return (
      <TableRow key={key || label}>
        <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>
          {t(label)}
        </TableCell>
        <TableCell sx={{ textAlign: 'right' }}>{displayValue}</TableCell>
      </TableRow>
    );
  };

  const renderStatusChip = (status: string) => (
    <Chip 
      label={status === 'active' ? t('active') : t('inactive')}
      color={status === 'active' ? 'success' : 'default'}
      size="small"
      sx={{ mr: 1 }}
    />
  );

  return (
    <Container maxWidth="lg" sx={{ py: 4, direction: 'rtl' }}>
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate(-1)}
        sx={{ mb: 2 }}
      >
        {t('backToList')}
      </Button>

      <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 4 }}>
          {/* Image Section */}
          <Box sx={{ width: { xs: '100%', md: '50%' } }}>
            {currentListing.image ? (
              <CardMedia
                component="img"
                height="400"
                image={currentListing.image}
                alt={currentListing.title}
                sx={{ borderRadius: 1, objectFit: 'cover' }}
              />
            ) : (
              <Box 
                height={400} 
                display="flex" 
                alignItems="center" 
                justifyContent="center"
                bgcolor="action.hover"
                borderRadius={1}
              >
                <Typography color="text.secondary">{t('noImage')}</Typography>
              </Box>
            )}
          </Box>

          {/* Details Section */}
          <Box sx={{ width: { xs: '100%', md: '50%' } }}>
            <Typography variant="h4" component="h1" gutterBottom sx={{ textAlign: 'right' }}>
              {currentListing.title}
            </Typography>
            
            <Typography variant="h5" color="primary" gutterBottom>
              {new Intl.NumberFormat('he-IL', { 
                style: 'currency', 
                currency: 'ILS',
                maximumFractionDigits: 0 
              }).format(currentListing.price)}
            </Typography>

            <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2, textAlign: 'right' }}>
              {t('specifications')}
            </Typography>
            <TableContainer component={Paper} sx={{ mb: 4, direction: 'rtl' }}>
              <Table>
                <TableBody>
                  {currentListing.brand_name && (
                    <TableRow>
                      <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('brand')}</TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>{currentListing.brand_name}</TableCell>
                    </TableRow>
                  )}
                  {currentListing.model_name && (
                    <TableRow>
                      <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('model')}</TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>{currentListing.model_name}</TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('year')}</TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>{currentListing.year}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('price')}</TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>₪{currentListing.price?.toLocaleString()}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('mileage')}</TableCell>
                    <TableCell sx={{ textAlign: 'right' }}>{currentListing.mileage?.toLocaleString()} {t('km')}</TableCell>
                  </TableRow>
                  {currentListing.transmission && (
                    <TableRow>
                      <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>{t('transmission')}</TableCell>
                      <TableCell sx={{ textAlign: 'right' }}>{t(currentListing.transmission.toLowerCase())}</TableCell>
                    </TableRow>
                  )}
                  {currentListing.fuel_type && 
                    renderSpecification(
                      'fuelType', 
                      t(currentListing.fuel_type.toLowerCase())
                    )
                  }
                  {currentListing.color && 
                    renderSpecification('color', currentListing.color)
                  }
                  {currentListing.status && 
                    renderSpecification(
                      'status', 
                      renderStatusChip(currentListing.status),
                      'status-row'
                    )
                  }
                  {currentListing.last_scraped_at && 
                    renderSpecification(
                      'lastScraped',
                      formatDate(currentListing.last_scraped_at),
                      'last-scraped'
                    )
                  }
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </Box>

        {/* Description Section */}
        {currentListing.description && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" gutterBottom>
              {t('carDescription')}
            </Typography>
            <Paper variant="outlined" sx={{ p: 3, whiteSpace: 'pre-line' }}>
              <Typography variant="body1">
                {currentListing.description}
              </Typography>
            </Paper>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default ListingDetail;
