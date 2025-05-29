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
  useMediaQuery
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { Outlet, Link as RouterLink, useLocation } from 'react-router-dom';

const Layout: React.FC = () => {
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

  const menuItems = [
    { name: 'Home', path: '/' },
    { name: 'Listings', path: '/listings' },
    { name: 'Brands', path: '/brands' },
    { name: 'About', path: '/about' },
    { name: 'Contact', path: '/contact' }
  ];


  return (
    <Box sx={{ flexGrow: 1 }}>
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
            <Box sx={{ display: 'flex', gap: 1 }}>
              {menuItems.map((item) => (
                <Button
                  key={item.name}
                  component={RouterLink}
                  to={item.path}
                  variant={location.pathname === item.path ? 'contained' : 'text'}
                  color="primary"
                  sx={{
                    textTransform: 'none',
                    fontWeight: location.pathname === item.path ? 600 : 400,
                    px: 2,
                  }}
                >
                  {item.name}
                </Button>
              ))}
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
