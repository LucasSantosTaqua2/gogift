// Define a estrutura do Comprador
export interface OwnerInfo {
  id: number;
  username: string;
}

// Define a estrutura do cabeçalho do pedido
export interface OrderInfo {
  owner_id: number;
  owner?: OwnerInfo; 
  created_at: string; 
  status?: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'REFUNDED';
}

// --- NOVO ---
export interface OrderGiftItem {
  recipient_name: string;
  quantity: number;
}

// Define a estrutura de um item dentro do pedido
export interface OrderItem {
  id: string; 
  register_giftcard_id: string; 
  enterprise_id: number;
  quantity: number;
  unit_price: number; 
  seller_amount: number;
  final_giftcard_codes: string | null;
  used_codes: string | null; 
  status: 'VALID' | 'USED' | 'PARTIALLY_USED'; 
  original_giftcard: { 
    title: string;
    imageUrl: string | null; 
    valor: number;
    desired_amount: number; 
  };
  order?: OrderInfo; 
  user_rating?: number;
  // --- NOVO ---
  gift_items?: OrderGiftItem[]; 
}

export interface Order {
  id: string; 
  owner_id: number;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'REFUNDED'; 
  total_amount: number; 
  net_amount?: number; 
  created_at: string;
  items: OrderItem[]; 
  owner?: OwnerInfo;
}