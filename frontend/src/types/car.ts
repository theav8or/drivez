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
  yad2_id: string;
  brand_id: number;
  model_id: number;
  title: string;
  description: string;
  price: number;
  original_price?: number;
  is_price_negotiable: boolean;
  year: number;
  mileage: number;
  fuel_type?: string;
  transmission?: string;
  body_type?: string;
  color?: string;
  engine_volume?: number;
  horsepower?: number;
  doors?: number;
  seats?: number;
  is_imported: boolean;
  is_accident_free: boolean;
  test_until?: string;
  city?: string;
  neighborhood?: string;
  location: string;
  thumbnail_url?: string;
  source_url: string;
  source_created_at?: string;
  source_updated_at?: string;
  status: 'active' | 'sold' | 'pending' | 'inactive' | 'expired';
  created_at: string;
  updated_at: string;
  last_seen_at: string;
  metadata?: Record<string, any>;
  // Relations
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
