import { Component, OnInit, signal, computed, effect } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { GiftcardService } from '../../../services/giftcard.service';
import { NavBarComponent } from '../shared/nav-bar/nav-bar.component';
import { FooterComponent } from '../shared/footer/footer.component';
import { NotificationService } from '../../../services/notification.service';
import { Category } from '../../models/category.model';
import { CategoryService } from '../../../services/category.service';
import { ImageCroppedEvent, ImageCropperComponent } from 'ngx-image-cropper';
import { Title } from '@angular/platform-browser';

@Component({
  selector: 'app-edit-gc',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NavBarComponent,
    FooterComponent,
    ImageCropperComponent,
    DatePipe,
    RouterLink
  ],
  templateUrl: './edit-gc.component.html',
  styleUrls: ['./edit-gc.component.css']
})
export class EditGcComponent implements OnInit {
  giftCardId: string | null = null;
  titulo: string = '';
  descricao: string = '';
  quantidade: number = 1;
  gerarCodigo: boolean = true;
  codigosManuais: string = '';
  imageSrc: string | null = null; 
  
  isLoading: boolean = true;
  isUploading: boolean = false;

  ativo: boolean = true;
  validade: string = ''; 
  nota: number | null = null;

  categories: Category[] = [];
  categoryId: number | null = null;

  // Propriedade para controlar se o produto tem vendas (bloqueia edição)
  hasSales: boolean = false;

  // --- VARIÁVEIS PARA O EDITOR DE IMAGEM ---
  imageChangedEvent: any = '';
  croppedImage: Blob | null = null; 
  showCropper = false; 

  // --- PROPRIEDADES PARA CÁLCULO DE PREÇO ---
  desiredAmount = signal<number | null>(null);
  
  calculatedSellingPrice = computed<number>(() => {
    const desired = this.desiredAmount();
    return desired && this.giftcardService ? this.giftcardService.calculateSellingPrice(desired) : 0;
  });

  constructor(
    private giftcardService: GiftcardService,
    private route: ActivatedRoute,
    private router: Router,
    private notificationService: NotificationService,
    private categoryService: CategoryService,
    private titleService: Title
  ) {
      effect(() => {
        
      });
  }

  ngOnInit(): void {
    this.titleService.setTitle("GoGift - Editar Gift Card");
    this.loadCategories();
    this.giftCardId = this.route.snapshot.paramMap.get('id');
    if (this.giftCardId) {
      this.loadGiftCardData(this.giftCardId);
    } else {
        this.isLoading = false;
        this.notificationService.show("ID do Gift Card não encontrado.", "error");
        this.router.navigate(['/dashboard-gc']);
    }
  }

   loadCategories(): void {
    this.categoryService.getCategories().subscribe({
      next: (data) => { this.categories = data; },
      error: (err) => { console.error('Erro ao carregar categorias', err); }
    });
  }

  loadGiftCardData(id: string): void {
      this.isLoading = true;
      this.giftcardService.getGiftCardById(id).subscribe({
        next: (data) => {
          this.titulo = data.title;
          this.descricao = data.description || '';
          this.quantidade = data.quantityavailable;
          this.desiredAmount.set(data.desired_amount); 
          this.gerarCodigo = data.generaterandomly;
          this.codigosManuais = data.codes || '';
          this.ativo = data.ativo;
          
          this.validade = data.validade ? new Date(data.validade).toISOString().split('T')[0] : '';
          this.categoryId = data.category_id ?? null;

          this.hasSales = !!data.has_sales;

          if (this.hasSales) {
             this.notificationService.show("Este produto possui vendas. Título e Valor não podem ser alterados.", "info");
          }

          if (data.imageUrl) {
            this.imageSrc = `http://127.0.0.1:8000/uploads/${data.imageUrl}`;
          }

          this.isLoading = false;
        },
        error: (err) => {
          console.error("Erro ao carregar dados para edição:", err);
          this.notificationService.show("Não foi possível carregar o Gift Card.", "error");
          this.isLoading = false;
          this.router.navigate(['/dashboard-gc']);
        }
      });
  }
  
  onFileSelected(event: Event): void {
      const element = event.currentTarget as HTMLInputElement;
      let fileList: FileList | null = element.files;
      if (fileList && fileList.length > 0) {
          this.imageChangedEvent = event;
          this.showCropper = true;
      }
  }

  imageCropped(event: ImageCroppedEvent) {
      if (event.blob) {
        this.croppedImage = event.blob;
        const reader = new FileReader();
        reader.onload = () => {
          this.imageSrc = reader.result as string;
        };
        reader.readAsDataURL(event.blob);
      }
  }

  confirmCrop() {
     this.showCropper = false;
  }


  cancelCrop() {
      this.imageChangedEvent = '';
      this.croppedImage = null; 
      this.showCropper = false;
      
      if(this.giftCardId) {
          this.giftcardService.getGiftCardById(this.giftCardId).subscribe(data => {
               if (data.imageUrl) {
                   this.imageSrc = `http://127.0.0.1:8000/uploads/${data.imageUrl}`;
               } else {
                   this.imageSrc = null; 
               }
          });
      } else {
          this.imageSrc = null;
      }
      
      const fileInput = document.getElementById('fileInput') as HTMLInputElement;
      if(fileInput) fileInput.value = '';
  }

  loadImageFailed() {
    this.notificationService.show('Não foi possível carregar a imagem. Tente outro arquivo.', 'error');
    this.showCropper = false;
    this.cancelCrop();
  }

  toggleGerarCodigo() {
     this.gerarCodigo = !this.gerarCodigo;
    if (!this.gerarCodigo) {
      this.atualizarQuantidadePelosCodigos();
    }
  }

  atualizarQuantidadePelosCodigos(): void {
    if (this.gerarCodigo) return;
    const codigos = this.codigosManuais?.split(';').filter(c => c.trim() !== '') || [];
    this.quantidade = codigos.length;
  }

  onDesiredAmountChange(value: string | null): void {
    const numericValue = value === null || value === '' ? null : parseFloat(value);
    this.desiredAmount.set(numericValue);
  }

  onSubmit(): void {
    if (!this.giftCardId) return;

    if (!this.gerarCodigo) {
        this.atualizarQuantidadePelosCodigos();
    }

    const currentDesiredAmount = this.desiredAmount();

    if (!this.titulo || this.quantidade < 1 || currentDesiredAmount === null || currentDesiredAmount <= 0) {
      this.notificationService.show('Preencha Título, Quantidade e um Valor Desejado válido.', 'warning');
      return;
    }

    this.isUploading = true;
    const formData = new FormData();
    
    formData.append('title', this.titulo);
    formData.append('desired_amount', currentDesiredAmount.toString());
    formData.append('description', this.descricao);
    formData.append('quantityavailable', this.quantidade.toString());
    formData.append('generaterandomly', String(this.gerarCodigo));
    formData.append('ativo', String(this.ativo));
    
    if (this.categoryId !== null && this.categoryId !== undefined) {
      formData.append('category_id', this.categoryId.toString());
    }
    if (this.validade) {
      formData.append('validade', this.validade);
    }
    if (this.nota !== null && this.nota !== undefined) {
      formData.append('nota', this.nota.toString());
    }
    if (!this.gerarCodigo) {
      const validCodes = this.codigosManuais.split(';').filter(c => c.trim() !== '').join(';');
      formData.append('codes', validCodes);
    }

    if (this.croppedImage instanceof Blob) {
      const filename = `${this.titulo.replace(/[^a-zA-Z0-9]/g, '-') || 'edited-image'}.jpg`;
      formData.append('image', this.croppedImage, filename);
    }

    this.giftcardService.updateGiftCard(this.giftCardId, formData).subscribe({
      next: () => {
        this.notificationService.show('Gift Card atualizado com sucesso!', "success");
        this.router.navigate(['/dashboard-gc']);
      },
      error: (err) => {
        const errorMessage = err.error?.detail || "Ocorreu um erro ao atualizar.";
        this.notificationService.show(errorMessage, "error");
        this.isUploading = false;
      },
      complete: () => {
        this.isUploading = false;
      }
    });
  }
}