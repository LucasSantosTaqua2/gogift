import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OrderService } from '../../../../services/order.service';

import { NotificationService } from '../../../../services/notification.service';
import { Order } from '../../../models/order.model';

@Component({
  selector: 'app-admin-orders',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-orders.component.html',
  styleUrls: ['./admin-orders.component.css']
})
export class AdminOrdersComponent implements OnInit {
  orders: Order[] = [];
  isLoading = false;
  
  // Filtros
  selectedStatus: string | undefined;
  selectedMonth: number | undefined;
  selectedYear: number | undefined;
  searchBuyer: string = '';
  
  // Estatísticas
  totalRevenue = 0; // Faturamento Bruto (Total pago pelos clientes)
  totalOrders = 0;
  totalPlatformProfit = 0; // NOVO: Lucro Líquido da Plataforma

  months = [
    { name: 'Janeiro', value: 1 }, { name: 'Fevereiro', value: 2 }, { name: 'Março', value: 3 },
    { name: 'Abril', value: 4 }, { name: 'Maio', value: 5 }, { name: 'Junho', value: 6 },
    { name: 'Julho', value: 7 }, { name: 'Agosto', value: 8 }, { name: 'Setembro', value: 9 },
    { name: 'Outubro', value: 10 }, { name: 'Novembro', value: 11 }, { name: 'Dezembro', value: 12 }
  ];
  
  availableYears: number[] = [];

  constructor(
    private orderService: OrderService,
    private notificationService: NotificationService
  ) {}

  ngOnInit(): void {
    this.generateYearOptions();
    this.loadOrders();
  }

  generateYearOptions(): void {
    const currentYear = new Date().getFullYear();
    for (let i = 0; i < 5; i++) {
      this.availableYears.push(currentYear - i);
    }
  }

  loadOrders(): void {
    this.isLoading = true;
    this.orderService.getAllOrdersAdmin(
      this.selectedStatus, 
      this.selectedMonth, 
      this.selectedYear, 
      this.searchBuyer
    ).subscribe({
      next: (data) => {
        this.orders = data;
        this.calculateStats();
        this.isLoading = false;
      },
      error: (err) => {
        this.notificationService.show('Erro ao carregar pedidos.', 'error');
        this.isLoading = false;
      }
    });
  }

  calculateStats(): void {
    this.totalOrders = this.orders.length;
    
    // Reseta totais
    this.totalRevenue = 0;
    this.totalPlatformProfit = 0;

    this.orders.forEach(order => {
      // Só somamos valores financeiros de pedidos Aprovados
      if (order.status === 'APPROVED') {
        this.totalRevenue += Number(order.total_amount);
        this.totalPlatformProfit += this.calculateOrderProfit(order);
      }
    });
  }

  // --- LÓGICA DE CÁLCULO DE LUCRO ---
  calculateOrderProfit(order: Order): number {
    // Se não tem net_amount (ex: pendente ou erro), lucro é zero ou incalculável
    if (!order.net_amount) return 0;

    // Soma quanto temos que pagar aos vendedores (seller_amount de cada item)
    const totalPayableToSellers = order.items.reduce((sum, item) => {
      return sum + Number(item.seller_amount);
    }, 0);

    // Lucro = O que entrou no banco (net_amount) - O que devemos aos vendedores
    return Number(order.net_amount) - totalPayableToSellers;
  }

  applyFilters(): void {
    this.loadOrders();
  }

  clearFilters(): void {
    this.selectedStatus = undefined;
    this.selectedMonth = undefined;
    this.selectedYear = undefined;
    this.searchBuyer = '';
    this.loadOrders();
  }

  getStatusClass(status: string): string {
    switch(status) {
      case 'APPROVED': return 'status-approved';
      case 'PENDING': return 'status-pending';
      case 'REJECTED': return 'status-rejected';
      case 'REFUNDED': return 'status-refunded';
      case 'EXPIRED': return 'status-expired';
      default: return '';
    }
  }
}