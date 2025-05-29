import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../store';
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
  Divider,
  CardMedia,
  Chip,
  Stack,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const ListingDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  
  const currentListing = useAppSelector(selectCurrentListing);
  const loading = useAppSelector(selectCarLoading);
  const error = useAppSelector(selectCarError);

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
      <Alert severity="error" sx={{ m: 2 }}>
        <AlertTitle>שגיאה</AlertTitle>
        {error}
      </Alert>
    );
  }

  if (!currentListing) {
    return (
      <Alert severity="warning" sx={{ m: 2 }}>
        <AlertTitle>לא נמצאה מודעה</AlertTitle>
        המודעה המבוקשת לא נמצאה
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

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate(-1)}
        sx={{ mb: 3 }}
      >
        חזור לרשימה
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
                sx={{
                  borderRadius: 1,
                  objectFit: 'cover',
                  width: '100%',
                }}
              />
            ) : (
              <Box
                sx={{
                  height: 400,
                  bgcolor: 'grey.200',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 1,
                }}
              >
                <Typography variant="body1" color="textSecondary">
                  אין תמונה זמינה
                </Typography>
              </Box>
            )}
          </Box>

          {/* Details Section */}
          <Box sx={{ width: { xs: '100%', md: '50%' } }}>
            <Typography variant="h4" component="h1" gutterBottom>
              {currentListing.title}
            </Typography>
            
            <Typography variant="h5" color="primary" gutterBottom>
              {new Intl.NumberFormat('he-IL', { 
                style: 'currency', 
                currency: 'ILS',
                maximumFractionDigits: 0 
              }).format(currentListing.price)}
            </Typography>

            <Divider sx={{ my: 3 }} />

            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableBody>
                  <TableRow>
                    <TableCell component="th" scope="row">שנת ייצור</TableCell>
                    <TableCell align="left">{currentListing.year}</TableCell>
                  </TableRow>
                  {currentListing.mileage && (
                    <TableRow>
                      <TableCell component="th" scope="row">קילומטרז</TableCell>
                      <TableCell align="left">
                        {currentListing.mileage.toLocaleString('he-IL')} ק"מ
                      </TableCell>
                    </TableRow>
                  )}
                  {currentListing.fuel_type && (
                    <TableRow>
                      <TableCell component="th" scope="row">סוג דלק</TableCell>
                      <TableCell align="left">{currentListing.fuel_type}</TableCell>
                    </TableRow>
                  )}
                  {currentListing.body_type && (
                    <TableRow>
                      <TableCell component="th" scope="row">סוג רכב</TableCell>
                      <TableCell align="left">{currentListing.body_type}</TableCell>
                    </TableRow>
                  )}
                  {currentListing.transmission && (
                    <TableRow>
                      <TableCell component="th" scope="row">תיבת הילוכים</TableCell>
                      <TableCell align="left">{currentListing.transmission}</TableCell>
                    </TableRow>
                  )}
                  {currentListing.color && (
                    <TableRow>
                      <TableCell component="th" scope="row">צבע</TableCell>
                      <TableCell align="left">
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Box 
                            sx={{
                              width: 20,
                              height: 20,
                              bgcolor: currentListing.color.toLowerCase(),
                              border: '1px solid #ccc',
                              borderRadius: '50%',
                            }}
                          />
                          <span>{currentListing.color}</span>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  )}
                  {currentListing.status && (
                    <TableRow>
                      <TableCell component="th" scope="row">סטטוס</TableCell>
                      <TableCell align="left">
                        <Chip 
                          label={currentListing.status === 'active' ? 'פעיל' : 'לא פעיל'} 
                          color={currentListing.status === 'active' ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  )}
                  {currentListing.last_scraped_at && (
                    <TableRow>
                      <TableCell component="th" scope="row">נמצא לאחרונה</TableCell>
                      <TableCell align="left">
                        {formatDate(currentListing.last_scraped_at)}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </Box>

        {/* Description Section */}
        {currentListing.description && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" gutterBottom>
              תיאור הרכב
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
