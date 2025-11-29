import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HowToSellComponent } from './how-to-sell.component';

describe('HowToSellComponent', () => {
  let component: HowToSellComponent;
  let fixture: ComponentFixture<HowToSellComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HowToSellComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HowToSellComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
