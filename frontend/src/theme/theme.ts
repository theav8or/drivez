import { createTheme } from '@mui/material/styles';
import { heIL } from '@mui/material/locale';

export const theme = createTheme(
  {
    direction: 'rtl',
    typography: {
      fontFamily: [
        'Heebo',
        '-apple-system',
        'BlinkMacSystemFont',
        '"Segoe UI"',
        'Roboto',
        '"Helvetica Neue"',
        'Arial',
        'sans-serif',
      ].join(','),
    },
    components: {
      MuiTypography: {
        styleOverrides: {
          root: {
            fontFamily: 'Heebo, Arial, sans-serif',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            fontFamily: 'Heebo, Arial, sans-serif',
          },
        },
      },
    },
  },
  heIL // Hebrew locale
);
