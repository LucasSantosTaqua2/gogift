import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { NavBarComponent } from '../shared/nav-bar/nav-bar.component';
import { FooterComponent } from '../shared/footer/footer.component';

@Component({
  selector: 'app-how-to-sell',
  standalone: true,
  imports: [CommonModule, NavBarComponent, FooterComponent, RouterLink],
  templateUrl: './how-to-sell.component.html',
  styleUrls: ['./how-to-sell.component.css']
})
export class HowToSellComponent implements OnInit {

  constructor(private titleService: Title) { }

  ngOnInit(): void {
    this.titleService.setTitle("GoGift | Como Vender");
    // window.scrollTo(0, 0);
  }
}