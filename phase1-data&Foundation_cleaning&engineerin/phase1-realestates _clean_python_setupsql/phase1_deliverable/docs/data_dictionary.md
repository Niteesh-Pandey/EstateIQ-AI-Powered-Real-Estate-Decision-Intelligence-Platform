# Data Dictionary

## cities
| Column | Type | Description |
|---|---|---|
| city_id | INT PK | Unique city identifier |
| city_name | TEXT | City name |
| state | TEXT | State/province |
| population | BIGINT | City population |
| average_income | NUMERIC | Average annual household income (₹) |
| development_score | NUMERIC | 0-100 composite development index |

## localities
| Column | Type | Description |
|---|---|---|
| locality_id | INT PK | Unique locality identifier |
| city_id | INT FK -> cities | Parent city |
| latitude/longitude | NUMERIC | Geo-coordinates |
| connectivity_score | NUMERIC | 0-100, transit/road connectivity |
| safety_score | NUMERIC | 0-100 |
| infrastructure_score | NUMERIC | 0-100 |
| development_score | NUMERIC | 0-100 composite, drives price/demand |
| commercial_score | NUMERIC | 0-100, commercial activity density |

## developers
| developer_id PK | rating (1-5) | delivery_score (0-100) | quality_score (0-100) | market_share (%) |

## projects
| project_id PK | developer_id FK | locality_id FK | launch_date | completion_date |
| total_units | units_sold | units_available | project_status |

## properties
| property_id PK | project_id FK | property_type | bedrooms | bathrooms | area_sqft |
| floor | total_floors | age_years | asking_price | monthly_rent |

## transactions
| transaction_id PK | property_id FK | transaction_date | transaction_price | price_per_sqft | buyer_type |

## rentals
| rental_id PK | property_id FK | rental_date | monthly_rent | vacancy_days | lease_duration |

## listing_history
| listing_id PK | property_id FK | listing_date | asking_price | status | days_on_market |

## market_monthly (locality_id, month) composite PK
| average_price_sqft | median_price_sqft | demand_index | supply_index |
| units_sold | available_inventory | absorption_rate | average_days_on_market |

## economic_monthly (month PK)
| interest_rate | mortgage_rate | inflation | unemployment | gdp_growth | income_growth |

## infrastructure
| infrastructure_id PK | locality_id FK | type (Metro/Airport/Highway/...) | impact_score |

## property_events
| event_id PK | property_id FK | event_type (View/Inquiry/Lead/Site Visit/Booking/Cancellation) |

## expenses
| expense_id PK | property_id FK | property_tax | maintenance | insurance | management_cost |

## documents (RAG source)
| document_id PK | source | document_date | city | locality | topic | text | embedding (pgvector) |

---

## Known limitations of this synthetic dataset
- `days_on_market` in `listing_history` was generated independent of property
  features, so the Days-on-Market and Sale-Probability ML models (Phase 7,
  Models 5 & 6) show weak/near-random performance (R² ≈ -0.04, AUC ≈ 0.50).
  This is disclosed rather than hidden — in a production build, DOM should be
  derived from actual demand/supply/pricing-gap signals so the models have
  real structure to learn.
- Risk Model (Model 7) is a transparent weighted composite, not an ML
  classifier, because no historical default/failure labels exist in this
  single-generation synthetic dataset. This is standard practice in real
  estate risk scoring when labeled outcomes are scarce — see
  `ml_artifacts/risk_model_spec.json`.
- Scale is a portfolio-demo scale (~90K rows across 14 tables), not full
  production scale (100K-500K+ transactions). `data/generate_data.py` and
  `generate_data_part2.py` constants (`N_PROPERTIES`, etc.) can be increased
  to reach production scale — logic doesn't change, only runtime.
