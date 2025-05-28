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
  source: string;
  source_id: string;
  title: string;
  price: number;
  mileage: number;
  year: number;
  location: string;
  description: string;
  url: string;
  created_at: string;
  updated_at: string;
}

export interface CarListingFilters {
  brand?: string;
  model?: string;
  minPrice?: number;
  maxPrice?: number;
  minYear?: number;
  maxYear?: number;
  location?: string;
  page?: number;
  limit?: number;
}
