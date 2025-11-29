import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Order } from '../app/models/order.model'; // Importe o novo modelo

@Injectable({
  providedIn: 'root'
})
export class OrderService {
  private apiUrl = '/api/orders';

  constructor(private http: HttpClient) { }

  getMyOrders(): Observable<Order[]> {
    return this.http.get<Order[]>(`${this.apiUrl}/me`);
  }

  getAllOrdersAdmin(status?: string, month?: number, year?: number, buyerName?: string): Observable<Order[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (month) params = params.set('month', month.toString());
    if (year) params = params.set('year', year.toString());
    if (buyerName) params = params.set('buyer_name', buyerName);

    return this.http.get<Order[]>(`${this.apiUrl}/admin/all`, { params });
  }
}