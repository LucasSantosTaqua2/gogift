// src/services/cart.service.ts
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { GiftCard } from './giftcard.service';
import { NotificationService } from './notification.service';

export interface GiftRecipient {
  name: string;
  email: string;
  quantity: number;
  message?: string;
}

export interface CartItem {
  product: GiftCard;
  quantity: number;
  gifts: GiftRecipient[]; // Nova propriedade
}

@Injectable({
  providedIn: 'root'
})
export class CartService {
  private cartItems: CartItem[] = [];
  private cartSubject = new BehaviorSubject<CartItem[]>([]);

  public cart$: Observable<CartItem[]> = this.cartSubject.asObservable();

  constructor(private notificationService: NotificationService) {
    const savedCart = localStorage.getItem('shoppingCart');
    if (savedCart) {
      this.cartItems = JSON.parse(savedCart);
      // Garante que itens antigos tenham o array de gifts
      this.cartItems.forEach(item => {
        if (!item.gifts) item.gifts = [];
      });
      this.cartSubject.next(this.cartItems);
    }
  }

  addToCart(product: GiftCard, quantity: number): void {
    const existingItem = this.cartItems.find(item => item.product.id === product.id);

    if (existingItem) {
      const newQuantity = existingItem.quantity + quantity;
      if (newQuantity > product.quantityavailable) {
        this.notificationService.show(`Estoque máximo (${product.quantityavailable}) atingido para este item.`, 'warning');
        existingItem.quantity = product.quantityavailable;
      } else {
        existingItem.quantity = newQuantity;
      }
    } else {
      if (quantity > product.quantityavailable) {
        this.notificationService.show(`Estoque insuficiente. Apenas ${product.quantityavailable} unidades disponíveis.`, 'warning');
        return;
      }
      // Inicializa com lista de presentes vazia
      this.cartItems.push({ product, quantity, gifts: [] });
    }
    
    this.saveCart();
    this.notificationService.show(`${product.title} adicionado ao carrinho!`, 'success');
  }

  updateQuantity(productId: string, newQuantity: number): void {
    const itemIndex = this.cartItems.findIndex(item => item.product.id === productId);
    if (itemIndex > -1) {
      const item = this.cartItems[itemIndex];
      if (newQuantity > item.product.quantityavailable) {
        this.notificationService.show(`Estoque máximo (${item.product.quantityavailable}) atingido.`, 'warning');
        item.quantity = item.product.quantityavailable;
      } else if (newQuantity < 1) {
        this.cartItems.splice(itemIndex, 1);
      } else {
        item.quantity = newQuantity;
        // Validação extra: se diminuir a quantidade total, verificar se os presentes ainda cabem
        const totalGifts = item.gifts.reduce((sum, g) => sum + g.quantity, 0);
        if (totalGifts > item.quantity) {
             // Remove presentes excedentes ou limpa lista (opção simplificada: limpar para evitar inconsistência)
             item.gifts = [];
             this.notificationService.show('A quantidade de itens diminuiu. Os presentes foram redefinidos.', 'info');
        }
      }
      this.saveCart();
    }
  }

  removeItem(productId: string): void {
    const itemIndex = this.cartItems.findIndex(item => item.product.id === productId);
    if (itemIndex > -1) {
      this.cartItems.splice(itemIndex, 1);
      this.saveCart();
      this.notificationService.show('Item removido do carrinho.', 'info');
    }
  }

  getCartItems(): CartItem[] {
    return this.cartItems;
  }

  clearCart(): void {
    this.cartItems = [];
    this.saveCart();
  }
  
  private saveCart(): void {
    localStorage.setItem('shoppingCart', JSON.stringify(this.cartItems));
    this.cartSubject.next(this.cartItems);
  }
}