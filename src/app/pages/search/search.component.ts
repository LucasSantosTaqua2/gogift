import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { switchMap } from 'rxjs/operators';
import { FormsModule } from '@angular/forms';

import { GiftcardService, GiftCard } from '../../../services/giftcard.service';
import { GiftCardTemplateComponent } from '../shared/gift-card-template/gift-card-template.component';
import { NavBarComponent } from '../shared/nav-bar/nav-bar.component';
import { FooterComponent } from '../shared/footer/footer.component';
import { CategoryService } from '../../../services/category.service';
import { Category } from '../../models/category.model';
import { Title } from '@angular/platform-browser';

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    NavBarComponent,
    FooterComponent,
    GiftCardTemplateComponent,
    FormsModule
  ],
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.css']
})
export class SearchComponent implements OnInit {
  private allGiftCards: GiftCard[] = []; 
  visibleGiftCards: GiftCard[] = []; 

  searchTerm: string | null = null;
  isLoading: boolean = true;
  categories: Category[] = [];

  // Configurações da paginação
  private readonly initialItems = 10; 
  private readonly itemsPerLoad = 5; 

  // Propriedades dos filtros
  selectedCategoryId: number | undefined;
  minPrice: number | undefined;
  maxPrice: number | undefined;
  sortBy: string | undefined;

  // Controle de visibilidade dos filtros no Mobile
  showMobileFilters: boolean = false;

  constructor(
    private giftcardService: GiftcardService,
    private categoryService: CategoryService,
    private route: ActivatedRoute,
    private router: Router,
    private titleService: Title
  ) {}

  ngOnInit(): void {
    this.titleService.setTitle("GoGift - Buscar");
    this.loadCategories();
    this.route.queryParamMap.pipe(
      switchMap(params => {
        this.isLoading = true;
        this.visibleGiftCards = []; 
        
        this.searchTerm = params.get('q');
        this.selectedCategoryId = params.has('category') ? Number(params.get('category')) : undefined;
        this.minPrice = params.has('minPrice') ? Number(params.get('minPrice')) : undefined;
        this.maxPrice = params.has('maxPrice') ? Number(params.get('maxPrice')) : undefined;
        this.sortBy = params.get('sortBy') || undefined;
        
        // Fecha os filtros automaticamente ao realizar uma busca no mobile
        this.showMobileFilters = false;

        return this.giftcardService.searchGiftCards(
            this.searchTerm || '',
            this.selectedCategoryId,
            this.minPrice,
            this.maxPrice,
            this.sortBy
        );
      })
    ).subscribe({
      next: (data) => {
        this.allGiftCards = data;
        this.visibleGiftCards = this.allGiftCards.slice(0, this.initialItems);
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Erro ao buscar gift cards:', err);
        this.allGiftCards = [];
        this.visibleGiftCards = [];
        this.isLoading = false;
      }
    });
  }
  
  loadCategories(): void {
    this.categoryService.getCategories().subscribe(data => {
      this.categories = data;
    });
  }

  toggleMobileFilters(): void {
    this.showMobileFilters = !this.showMobileFilters;
  }

  applyFilters(): void {
    const queryParams: any = {};
    if (this.searchTerm) queryParams.q = this.searchTerm;
    if (this.selectedCategoryId) queryParams.category = this.selectedCategoryId;
    if (this.minPrice !== undefined) queryParams.minPrice = this.minPrice;
    if (this.maxPrice !== undefined) queryParams.maxPrice = this.maxPrice;
    if (this.sortBy) queryParams.sortBy = this.sortBy;

    this.router.navigate(['/search'], { queryParams });
  }

  clearFilters(): void {
    this.selectedCategoryId = undefined;
    this.minPrice = undefined;
    this.maxPrice = undefined;
    this.sortBy = undefined;
    this.applyFilters();
  }

  loadMore(): void {
    const currentCount = this.visibleGiftCards.length;
    const newCards = this.allGiftCards.slice(currentCount, currentCount + this.itemsPerLoad);
    this.visibleGiftCards.push(...newCards);
  }
  
  get hasMoreItems(): boolean {
    return this.visibleGiftCards.length < this.allGiftCards.length;
  }
}