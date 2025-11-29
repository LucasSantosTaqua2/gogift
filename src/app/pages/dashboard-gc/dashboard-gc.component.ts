import { Component, OnInit } from '@angular/core';
import { CommonModule, DatePipe, CurrencyPipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GiftcardService, GiftCard } from '../../../services/giftcard.service';
import { NotificationService } from '../../../services/notification.service';
import { ConfirmationService } from '../../../services/confirmation.service';
import { FormsModule } from '@angular/forms';
import { OrderItem } from '../../models/order.model';
import { DashboardStats, EnterpriseService } from '../../../services/enterprise.service';
import { Title } from '@angular/platform-browser';
import { ZXingScannerModule } from '@zxing/ngx-scanner';
import { BarcodeFormat } from '@zxing/library';

@Component({
  selector: 'app-dashboard-gc',
  standalone: true,
  imports: [
      CommonModule,
      RouterLink,
      FormsModule,
      DatePipe,
      CurrencyPipe,
      DecimalPipe,
      ZXingScannerModule
    ],
  templateUrl: './dashboard-gc.component.html',
  styleUrls: ['./dashboard-gc.component.css']
})
export class DashboardGcComponent implements OnInit {
  activeComponent = 'componente1';

  myGiftCards: GiftCard[] = [];
  isLoading = true;

  validationCode: string = '';
  validationResult: OrderItem | null = null;
  isValidating: boolean = false;
  isPopupVisible = false;

  usedItemsHistory: OrderItem[] = [];
  isLoadingHistory: boolean = false;

  dashboardStats: DashboardStats | null = null;
  isLoadingStats: boolean = true;

  allSalesData: OrderItem[] = [];
  filteredSales: OrderItem[] = [];
  totalAmountReceived: number = 0;
  isLoadingSales: boolean = false;

  selectedProductFilter: string | undefined;
  selectedMonthFilter: number | undefined;
  selectedYearFilter: number | undefined;

  months: { name: string, value: number }[] = [
    { name: 'Janeiro', value: 1 }, { name: 'Fevereiro', value: 2 }, { name: 'Março', value: 3 },
    { name: 'Abril', value: 4 }, { name: 'Maio', value: 5 }, { name: 'Junho', value: 6 },
    { name: 'Julho', value: 7 }, { name: 'Agosto', value: 8 }, { name: 'Setembro', value: 9 },
    { name: 'Outubro', value: 10 }, { name: 'Novembro', value: 11 }, { name: 'Dezembro', value: 12 }
  ];
  availableYears: number[] = [];

  statusTranslations: { [key: string]: string } = {
    'APPROVED': 'Aprovado', 'PENDING': 'Pendente', 'REJECTED': 'Rejeitado',
    'EXPIRED': 'Expirado', 'REFUNDED': 'Estornado', 'VALID': 'Válido',
    'USED': 'Utilizado', 'PARTIALLY_USED': 'Parcialmente Utilizado'
  };

  // --- SCANNER ---
  isScanning: boolean = false;
  allowedFormats = [BarcodeFormat.QR_CODE];
  currentDevice: MediaDeviceInfo | undefined = undefined;
  availableDevices: MediaDeviceInfo[] = [];

  constructor(
    private giftcardService: GiftcardService,
    private notificationService: NotificationService,
    private confirmationService: ConfirmationService,
    private enterpriseService: EnterpriseService, 
    private titleService: Title
  ) { }

  ngOnInit(): void {
    this.titleService.setTitle("GoGift - Painel de Gift Cards");
    this.loadMyGiftCards();
    this.generateYearOptions();
    this.loadDashboardStats();
  }

  translateStatus(status: string): string {
    return this.statusTranslations[status] || status;
  }

  showComponent(name: string) {
    this.activeComponent = name;
    if (name === 'componente3' && this.allSalesData.length === 0) {
      this.loadSalesData();
    }
    if (name === 'componente2') {
      if (this.usedItemsHistory.length === 0) {
        this.loadUsedItemsHistory();
      }
    }
  }

  loadDashboardStats(): void {
    this.isLoadingStats = true;
    this.enterpriseService.getDashboardStats().subscribe({
      next: (data) => {
        this.dashboardStats = data;
        this.isLoadingStats = false;
      },
      error: (err) => {
        console.error("Erro ao carregar estatísticas:", err);
        this.dashboardStats = null;
        this.isLoadingStats = false;
      }
    });
  }

  loadMyGiftCards(): void {
    this.isLoading = true;
    this.giftcardService.getMyGiftCards().subscribe({
      next: (data) => {
        this.myGiftCards = data;
        this.myGiftCards.sort((a, b) => a.title.localeCompare(b.title));
        this.isLoading = false;
      },
      error: () => {
        this.notificationService.show('Erro ao carregar gift cards.', 'error');
        this.isLoading = false;
      }
    });
  }

 deleteGiftCard(id: string, title: string): void {
    this.confirmationService.confirm({
      title: 'Confirmação de Exclusão',
      message: `Tem certeza que deseja excluir "${title}"?`,
      confirmText: 'Excluir', 
      cancelText: 'Cancelar'
    }).subscribe(confirmed => {
      if (confirmed) {
        this.performDelete(id);
      }
    });
  }

  private performDelete(id: string): void {
    this.giftcardService.deleteGiftCard(id).subscribe({
      next: () => {
        this.notificationService.show('Gift card excluído!', 'success');
        this.myGiftCards = this.myGiftCards.filter(gc => gc.id !== id);
        if (this.activeComponent === 'componente3') {
          this.loadSalesData(); 
        }
      },
      error: (err) => {
        if (err.status === 409) {
           this.offerDeactivation(id);
        } else {
           const msg = err.error?.detail || 'Falha ao excluir.';
           this.notificationService.show(msg, 'error');
        }
      }
    });
  }

  private offerDeactivation(id: string): void {
    this.confirmationService.confirm({
      title: 'Não é possível excluir',
      message: 'Este produto possui vendas. Deseja marcá-lo como INATIVO?',
      confirmText: 'Inativar Produto',
      cancelText: 'Manter'
    }).subscribe(shouldDeactivate => {
      if (shouldDeactivate) {
        this.deactivateGiftCard(id);
      }
    });
  }

  private deactivateGiftCard(id: string): void {
    const gc = this.myGiftCards.find(g => g.id === id);
    if (!gc) return;

    const formData = new FormData();
    formData.append('title', gc.title);
    formData.append('desired_amount', gc.desired_amount.toString());
    formData.append('quantityavailable', gc.quantityavailable.toString());
    formData.append('ativo', 'false'); 
    
    if(gc.description) formData.append('description', gc.description);
    formData.append('generaterandomly', String(gc.generaterandomly));
    if (gc.codes) formData.append('codes', gc.codes);
    if (gc.category_id) formData.append('category_id', gc.category_id.toString());
    if (gc.validade) {
        formData.append('validade', gc.validade.toString().split('T')[0]);
    }

    this.giftcardService.updateGiftCard(id, formData).subscribe({
        next: (updatedGc) => {
            this.notificationService.show('Produto inativado.', 'success');
            const index = this.myGiftCards.findIndex(g => g.id === id);
            if (index !== -1) {
                this.myGiftCards[index] = updatedGc;
            }
        },
        error: (err) => {
            const msg = err.error?.detail || 'Erro ao inativar.';
            this.notificationService.show(msg, 'error');
        }
    });
  }

  generateYearOptions(): void {
    const currentYear = new Date().getFullYear();
    for (let i = 0; i < 5; i++) {
      this.availableYears.push(currentYear - i);
    }
    this.availableYears.sort((a, b) => b - a);
  }

  loadSalesData(): void {
    this.isLoadingSales = true;
    this.enterpriseService.getEnterpriseSalesHistory(
      this.selectedProductFilter,
      this.selectedMonthFilter,
      this.selectedYearFilter
    ).subscribe({
      next: (data: OrderItem[]) => {
        this.allSalesData = data;
        this.filteredSales = data;
        this.calculateTotalAmountReceived();
        this.isLoadingSales = false;
      },
      error: () => {
        this.notificationService.show('Erro ao carregar vendas.', 'error');
        this.allSalesData = [];
        this.filteredSales = [];
        this.totalAmountReceived = 0;
        this.isLoadingSales = false;
      }
    });
  }

  applySalesFilters(): void {
    this.loadSalesData();
  }

  clearSalesFilters(): void {
    this.selectedProductFilter = undefined;
    this.selectedMonthFilter = undefined;
    this.selectedYearFilter = undefined;
    this.loadSalesData();
  }

  calculateTotalAmountReceived(): void {
    this.totalAmountReceived = this.filteredSales.reduce((sum, item) => {
       return sum + Number(item.seller_amount || 0);
    }, 0);
  }

   loadUsedItemsHistory(): void {
    this.isLoadingHistory = true;
    this.giftcardService.getUsedGiftCardsHistory().subscribe({
      next: (data) => {
        this.usedItemsHistory = data.sort((a, b) =>
           new Date(b.order?.created_at || 0).getTime() - new Date(a.order?.created_at || 0).getTime()
        );
        this.isLoadingHistory = false;
      },
      error: () => {
        this.notificationService.show('Erro ao carregar histórico.', 'error');
        this.isLoadingHistory = false;
      }
    });
  }

  validateCode(): void {
    if (!this.validationCode.trim()) {
      this.notificationService.show('Insira um código.', 'warning');
      return;
    }
    this.isValidating = true;
    this.giftcardService.validateGiftCardCode(this.validationCode).subscribe({
      next: (data) => {
        this.validationResult = data;
        this.isPopupVisible = true;
        this.isValidating = false;
      },
      error: (err) => {
        this.notificationService.show(err.error.detail || 'Código inválido ou incorreto.', 'error');
        this.isValidating = false;
      }
    });
  }

  markAsUsed(): void {
    if (!this.validationResult || !['VALID', 'PARTIALLY_USED'].includes(this.validationResult.status)) {
        this.notificationService.show('Código não pode ser marcado.', 'warning');
        return;
    };
    const codeToMark = this.validationCode;
    this.giftcardService.markGiftCardCodeAsUsed(codeToMark).subscribe({
      next: (updatedItem) => {
        this.notificationService.show(`Código ${codeToMark} marcado como utilizado!`, 'success');
        this.closePopup();
        this.loadUsedItemsHistory();
        if (this.allSalesData.length > 0) {
            this.loadSalesData();
        }
      },
      error: (err) => this.notificationService.show(err.error.detail || 'Erro ao marcar código.', 'error')
    });
  }

  closePopup(): void {
    this.isPopupVisible = false;
    this.validationResult = null;
    this.validationCode = '';
  }

  // --- LÓGICA DO SCANNER ---

  toggleScanner(): void {
    this.isScanning = !this.isScanning;
    if (!this.isScanning) {
        this.currentDevice = undefined; 
    }
  }

  onCamerasFound(devices: MediaDeviceInfo[]): void {
    const backCameras = devices.filter(device => /back|rear|traseira|environment/gi.test(device.label));
    this.availableDevices = backCameras.length > 0 ? backCameras : devices;

    // Tenta evitar câmeras Wide/Ultra/0.5x
    let bestCamera = this.availableDevices.find(device => {
        const label = device.label.toLowerCase();
        return !label.includes('wide') && !label.includes('ultra') && !label.includes('0.5');
    });

    // Fallback: pega a última da lista (geralmente é a principal em Androids)
    if (!bestCamera && this.availableDevices.length > 0) {
        bestCamera = this.availableDevices[this.availableDevices.length - 1]; 
    }

    this.currentDevice = bestCamera || this.availableDevices[0];
  }

  switchCamera(): void {
    if (!this.availableDevices || this.availableDevices.length <= 1) return;

    const currentIndex = this.availableDevices.findIndex(d => d.deviceId === this.currentDevice?.deviceId);
    const nextIndex = (currentIndex + 1) % this.availableDevices.length;
    
    this.currentDevice = this.availableDevices[nextIndex];
    this.notificationService.show(`Câmera: ${this.currentDevice.label}`, 'success');
  }

  onCodeResult(resultString: string): void {
    console.log('Código lido:', resultString);
    this.validationCode = resultString;
    this.isScanning = false;
    this.currentDevice = undefined;
    this.validateCode(); 
  }
}