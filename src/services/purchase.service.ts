import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CartItem } from './cart.service';

export interface PreferenceResponse {
  preference_id: string;
  init_point: string;
}

@Injectable({
  providedIn: 'root'
})
export class PurchaseService {
  private apiUrl = 'http://127.0.0.1:8000/mercadopago'; // Ajuste conforme sua URL base

  constructor(private http: HttpClient) { }

  createCartPreference(items: CartItem[]): Observable<PreferenceResponse> {
    const body = {
      items: items.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity,
        // --- CORREÇÃO AQUI: Enviar a lista de presentes ---
        gifts: item.gifts || [] 
      }))
    };
    return this.http.post<PreferenceResponse>(`${this.apiUrl}/create_preference_cart`, body);
  }
}