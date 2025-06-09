import React, { useState } from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  Container, 
  Box, 
  Button,
  IconButton,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
  Select,
  FormControl,
  InputLabel
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LanguageIcon from '@mui/icons-material/Language';
import { Outlet, Link as RouterLink, useLocation } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';

const Layout: React.FC = () => {
  const { t, language, setLanguage } = useI18n();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLanguageChange = (event: any) => {
    setLanguage(event.target.value);
  };

  const menuItems = [
    { name: t('home'), path: '/' },
    { name: t('listings'), path: '/listings' },
    { name: t('brands'), path: '/brands' },
    { name: t('about'), path: '/about' },
    { name: t('contact'), path: '/contact' }
  ];
  
  const languages = [
    { code: 'en', name: 'English' },
    { code: 'he', name: 'עברית' }
  ];


  return (
    <Box sx={{ 
      flexGrow: 1,
      direction: 'rtl',
      textAlign: 'right',
      '& *': {
        fontFamily: 'Heebo, Arial, sans-serif !important',
      },
    }}>
      <AppBar 
        position="sticky" 
        elevation={0} 
        color="default" 
        sx={{ 
          borderBottom: '1px solid rgba(0, 0, 0, 0.12)', 
          bgcolor: 'background.paper',
          py: 1
        }}
      >
        <Toolbar disableGutters sx={{ width: '100%', maxWidth: 'lg', mx: 'auto', px: 2 }}>
          <Box 
            component={RouterLink} 
            to="/" 
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              textDecoration: 'none',
              mr: 2
            }}
          >
            <Typography
              variant="h6"
              noWrap
              component="div"
              sx={{
                fontWeight: 700,
                letterSpacing: '.1rem',
                color: 'primary.main',
              }}
            >
              DRIVEZ
            </Typography>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              {t('appTitle')}
            </Typography>
          </Box>

          <Box sx={{ flexGrow: 1 }} />
          
          {isMobile ? (
            <>
              <IconButton
                size="large"
                edge="start"
                color="inherit"
                aria-label="menu"
                onClick={handleMenuOpen}
                sx={{ color: 'text.primary' }}
              >
                <MenuIcon />
              </IconButton>
              <Menu
                id="mobile-menu"
                anchorEl={anchorEl}
                anchorOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                keepMounted
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                PaperProps={{
                  elevation: 3,
                  sx: {
                    mt: 1,
                    minWidth: 200,
                  },
                }}
              >
                {menuItems.map((item) => (
                  <MenuItem 
                    key={item.name} 
                    onClick={handleMenuClose}
                    component={RouterLink}
                    to={item.path}
                    selected={location.pathname === item.path}
                    sx={{
                      color: location.pathname === item.path ? 'primary.main' : 'text.primary',
                      '&:hover': {
                        backgroundColor: 'action.hover',
                      },
                    }}
                  >
                    {item.name}
                  </MenuItem>
                ))}
              </Menu>
            </>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 2 }}>
                {menuItems.map((item) => (
                  <Button
                    key={item.path}
                    color="inherit"
                    component={RouterLink}
                    to={item.path}
                    sx={{
                      textDecoration: 'none',
                      borderBottom: location.pathname === item.path ? '2px solid white' : 'none',
                      borderRadius: 0,
                      '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.1)'
                      }
                    }}
                  >
                    {item.name}
                  </Button>
                ))}
              </Box>
              <FormControl size="small" variant="standard" sx={{ minWidth: 100, color: 'white' }}>
                <Select
                  value={language}
                  onChange={handleLanguageChange}
                  inputProps={{ 'aria-label': 'Select language' }}
                  sx={{
                    color: 'white',
                    '& .MuiSelect-icon': {
                      color: 'white'
                    },
                    '&:before, &:after': {
                      borderBottomColor: 'white !important'
                    },
                    '&:hover:not(.Mui-disabled):before': {
                      borderBottomColor: 'white'
                    }
                  }}
                  IconComponent={LanguageIcon}
                >
                  {languages.map((lang) => (
                    <MenuItem key={lang.code} value={lang.code}>
                      {lang.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}
        </Toolbar>
      </AppBar>
      <Container sx={{ mt: 4, mb: 4 }}>
        <Outlet />
      </Container>
    </Box>
  );
};

export default Layout;
