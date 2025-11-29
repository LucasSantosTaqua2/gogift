import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NotificationService } from '../../../services/notification.service';
import { OrderService } from '../../../services/order.service';
import { Order, OrderItem } from '../../models/order.model';
import { Router, ActivatedRoute } from '@angular/router';
import { CartService } from '../../../services/cart.service';
import { GiftcardService } from '../../../services/giftcard.service'; 
import { FormsModule } from '@angular/forms'; 
import { QRCodeModule } from 'angularx-qrcode'; // <--- 1. IMPORT NOVO

@Component({
  selector: 'app-my-purchases',
  standalone: true,
  imports: [CommonModule, FormsModule, QRCodeModule], // <--- 2. ADICIONE AQUI
  templateUrl: './my-purchases.component.html',
  styleUrls: ['./my-purchases.component.css']
})
export class MyPurchasesComponent implements OnInit {
  approvedOrders: Order[] = [];
  pendingOrders: Order[] = [];
  isLoading = true;
  
  // Traduções de status
  statusTranslations: { [key: string]: string } = {
    'APPROVED': 'Aprovado', 'PENDING': 'Pendente', 'REJECTED': 'Rejeitado',
    'EXPIRED': 'Expirado', 'REFUNDED': 'Estornado',
    'VALID': 'Válido', 'USED': 'Utilizado', 'PARTIALLY_USED': 'Parcialmente Utilizado'
  };

  // Variáveis do Modal de Avaliação
  isRatingModalVisible = false;
  ratingProductId: string | null = null;
  ratingProductTitle: string = '';
  currentRating: number = 0;
  currentComment: string = '';

  // --- 3. VARIÁVEIS DO MODAL DE QR CODE (NOVO) ---
  isQrModalVisible = false;
  selectedQrCode: string = '';
  selectedQrProductTitle: string = '';

  constructor(
    private orderService: OrderService,
    private notificationService: NotificationService,
    private router: Router,
    private route: ActivatedRoute,
    private cartService: CartService,
    private giftcardService: GiftcardService 
  ) {}

  ngOnInit(): void {
    this.handlePaymentStatus();
    this.loadOrders();
  }

  translateStatus(status: string): string {
    return this.statusTranslations[status] || status;
  }

  private handlePaymentStatus(): void {
    this.route.queryParamMap.subscribe(params => {
        const status = params.get('status');
        if (status === 'approved' && sessionStorage.getItem('paymentProcessed') !== 'true') {
            this.notificationService.show('Pagamento aprovado com sucesso!', 'success');
            this.cartService.clearCart();
            sessionStorage.setItem('paymentProcessed', 'true');
            this.router.navigate([], {
                relativeTo: this.route,
                queryParams: { status: null },
                queryParamsHandling: 'merge'
            });
        }
        if (!status) {
            sessionStorage.removeItem('paymentProcessed');
        }
    });
  }

  loadOrders(): void {
    this.isLoading = true;
    this.orderService.getMyOrders().subscribe({
      next: (data) => {
        this.approvedOrders = data.filter(order => order.status === 'APPROVED');
        this.pendingOrders = data.filter(order => order.status === 'PENDING');
        this.isLoading = false;
      },
      error: () => {
        this.notificationService.show('Erro ao carregar seu histórico de compras.', 'error');
        this.isLoading = false;
      }
    });
  }

  // --- 4. FUNÇÕES DO QR CODE (NOVO) ---

  openQrModal(item: OrderItem): void {
    if (!item.final_giftcard_codes) {
        this.notificationService.show('Código ainda não disponível.', 'warning');
        return;
    }
    // Define os dados para o modal
    this.selectedQrCode = item.final_giftcard_codes;
    this.selectedQrProductTitle = item.original_giftcard.title;
    this.isQrModalVisible = true; // Abre o modal
  }

  closeQrModal(): void {
    this.isQrModalVisible = false;
    this.selectedQrCode = '';
  }

  copyCodeFromModal(): void {
    navigator.clipboard.writeText(this.selectedQrCode).then(() => {
        this.notificationService.show(`Código copiado!`, 'success');
    }).catch(err => {
        this.notificationService.show('Erro ao copiar código.', 'error');
    });
  }

  // --- Funções de Avaliação (Mantidas) ---
  
  openRatingModal(item: OrderItem): void {
    this.ratingProductId = item.register_giftcard_id; 
    this.ratingProductTitle = item.original_giftcard.title;
    this.currentRating = 0;
    this.currentComment = '';
    this.isRatingModalVisible = true;
  }

  closeRatingModal(): void {
    this.isRatingModalVisible = false;
    this.ratingProductId = null;
  }

  setRating(stars: number): void {
    this.currentRating = stars;
  }

  submitRating(): void {
    if (!this.ratingProductId || this.currentRating === 0) {
      this.notificationService.show('Selecione uma nota de 1 a 5.', 'warning');
      return;
    }

    this.giftcardService.rateProduct(this.ratingProductId, this.currentRating, this.currentComment).subscribe({
      next: () => {
        this.notificationService.show('Avaliação enviada com sucesso!', 'success');
        // Atualiza localmente para refletir na tela
        this.approvedOrders.forEach(order => {
          order.items.forEach(item => {
            if (item.register_giftcard_id === this.ratingProductId) {
              item.user_rating = this.currentRating;
            }
          });
        });
        this.closeRatingModal();
      },
      error: (err) => {
        const msg = err.error?.detail || 'Erro ao enviar avaliação.';
        this.notificationService.show(msg, 'error');
      }
    });
  }
}