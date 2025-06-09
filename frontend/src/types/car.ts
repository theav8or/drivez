export interface CarBrand {
  id: number;
  name: string;
  normalized_name: string;
}

export interface CarModel {
  id: number;
  brand_id: number;
  name: string;
  normalized_name: string;
}

export interface CarListing {
  id: number;
  model_id: number;
  brand_id: number;
  source: string;
  source_id: string;
  title: string;
  price: number;
  mileage: number;
  year: number;
  location: string;
  description: string;
  url: string;
  image?: string;
  created_at: string;
  updated_at: string;
  last_scraped_at?: string;
  fuel_type?: string;
  body_type?: string;
  transmission?: string;
  color?: string;
  status?: 'active' | 'sold' | 'pending' | 'inactive';
  brand_name?: string;
  model_name?: string;
}

export interface CarListingFilters {
  brand?: string;
  model?: string;
  minPrice?: number;
  maxPrice?: number;
  yearFrom?: number;
  yearTo?: number;
  location?: string;
  page?: number;
  limit?: number;
}
