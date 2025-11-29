// src/app/pages/cart/cart.component.ts
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms'; // Necessário para o formulário

import { NavBarComponent } from '../shared/nav-bar/nav-bar.component';
import { CartService, CartItem, GiftRecipient } from '../../../services/cart.service';
import { PurchaseService } from '../../../services/purchase.service';
import { NotificationService } from '../../../services/notification.service';
import { EmptyCartComponent } from '../empty-cart/empty-cart.component';
import { Title } from '@angular/platform-browser';

@Component({
  selector: 'app-cart',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    NavBarComponent,
    EmptyCartComponent,
    FormsModule // Importante
  ],
  templateUrl: './cart.component.html',
  styleUrls: ['./cart.component.css']
})
export class CartComponent implements OnInit {
  cartItems: CartItem[] = [];
  
  // Resumo financeiro
  totalProdutosBase: number = 0;   
  taxaPlataforma: number = 0;      
  subtotalComPlataforma: number = 0; 
  taxaServico: number = 0;        
  totalPedido: number = 0;        

  isLoading = false;

  // --- Lógica de Presentes ---
  openGiftFormId: string | null = null;
  newGift: GiftRecipient = { name: '', email: '', quantity: 1, message: '' };

  constructor(
    private cartService: CartService,
    private purchaseService: PurchaseService,
    private notificationService: NotificationService,
    private router: Router,
    private titleService: Title
  ) {}

  ngOnInit(): void {
    this.titleService.setTitle("GoGift - Carrinho");
    this.cartService.cart$.subscribe(items => {
      this.cartItems = items;
      this.calcularTotais();
    });
  }

  increaseQuantity(item: CartItem): void {
    this.cartService.updateQuantity(item.product.id, item.quantity + 1);
  }

  decreaseQuantity(item: CartItem): void {
    this.cartService.updateQuantity(item.product.id, item.quantity - 1);
  }

  removeItem(item: CartItem): void {
    this.cartService.removeItem(item.product.id);
  }

  // --- Métodos de Presente ---
  
  toggleGiftForm(item: CartItem): void {
    if (this.openGiftFormId === item.product.id) {
      this.openGiftFormId = null;
    } else {
      this.openGiftFormId = item.product.id;
      this.newGift = { name: '', email: '', quantity: 1, message: '' };
    }
  }

  getRemainingQuantity(item: CartItem): number {
    const giftsQty = (item.gifts || []).reduce((sum, g) => sum + g.quantity, 0);
    return item.quantity - giftsQty;
  }

  addGift(item: CartItem): void {
    if (!this.newGift.name || !this.newGift.email) {
      this.notificationService.show('Preencha nome e e-mail.', 'warning');
      return;
    }

    const remaining = this.getRemainingQuantity(item);
    if (this.newGift.quantity > remaining) {
      this.notificationService.show(`Você só tem mais ${remaining} unidades disponíveis para presente.`, 'warning');
      return;
    }

    if (!item.gifts) item.gifts = [];
    
    // Clona o objeto para não manter referência
    item.gifts.push({ ...this.newGift });

    // Limpa form e fecha
    this.newGift = { name: '', email: '', quantity: 1, message: '' };
    this.openGiftFormId = null;
    this.notificationService.show('Destinatário adicionado!', 'success');
  }

  removeGift(item: CartItem, index: number): void {
    item.gifts.splice(index, 1);
  }

  // ---------------------------

  calcularTotais(): void {
    this.totalProdutosBase = 0;
    this.taxaPlataforma = 0;
    this.subtotalComPlataforma = 0;

    this.cartItems.forEach(item => {
      const qtd = item.quantity;
      const valorVenda = Number(item.product.valor);
      const valorDesejado = Number(item.product.desired_amount);

      this.totalProdutosBase += valorDesejado * qtd;
      const taxaItem = Math.max(0, valorVenda - valorDesejado);
      this.taxaPlataforma += taxaItem * qtd;
      this.subtotalComPlataforma += valorVenda * qtd;
    });

    this.taxaServico = this.subtotalComPlataforma * 0.05;
    this.totalPedido = this.subtotalComPlataforma + this.taxaServico;
  }

  finalizarCompra(): void {
    if (this.cartItems.length === 0) {
      this.notificationService.show('Seu carrinho está vazio!', 'warning');
      return;
    }

    this.isLoading = true;
    this.notificationService.show('Redirecionando para o pagamento...', 'info');


    this.purchaseService.createCartPreference(this.cartItems).subscribe({
      next: (response) => {
        if (response && response.init_point) {
          window.location.href = response.init_point;
        } else {
          this.notificationService.show('Não foi possível iniciar o pagamento. Tente novamente.', 'error');
          this.isLoading = false;
        }
      },
      error: (err) => {
        const errorMessage = err.error?.detail || 'Ocorreu um erro desconhecido.';
        this.notificationService.show(`Erro: ${errorMessage}`, 'error');
        this.isLoading = false;
      }
    });
  }
}