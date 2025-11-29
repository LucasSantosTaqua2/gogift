import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

import { EnterpriseFormData } from '../../models/enterprise.model';

import { FooterComponent } from '../shared/footer/footer.component';
import { EnterpriseService } from '../../../services/enterprise.service';
import { NotificationService } from '../../../services/notification.service';
import { UserService } from '../../../services/user.service';
import { AuthService } from '../../../services/auth.service';
import { NgxMaskDirective } from 'ngx-mask';
import { Title } from '@angular/platform-browser';

@Component({
  selector: 'app-gc-guide',
  standalone: true,
  imports: [CommonModule, FormsModule, FooterComponent, NgxMaskDirective],
  templateUrl: './gc-guide.component.html',
  styleUrls: ['./gc-guide.component.css']
})
export class GcGuideComponent implements OnInit{
  enterprise: EnterpriseFormData  = {
    nome_fantasia: '',
    cnpj: '',
    nome_admin_empresa: '',
    cpf_adm: '',
    telefone: ''
  };

  isSubmitting = false; 

  constructor(
    private enterpriseService: EnterpriseService,
    private router: Router,
    private notificationService: NotificationService,
    private userService: UserService,
    private authService: AuthService, 
    private titleService: Title
  ) {}

   ngOnInit(): void {
    this.titleService.setTitle("GoGift - Parceiro");
    this.carregarDadosUsuario();
  }

  carregarDadosUsuario(): void {
    this.userService.getMe().subscribe({
      next: (userDetails) => {
        
        if (userDetails.role === 'ENTERPRISE' || userDetails.role === 'ADMIN') {
          this.notificationService.show('Você já tem permissão de vendedor.', 'info');
          this.router.navigate(['/dashboard-gc']);
          return;
        }


        if (userDetails.account_type === 'person') {
          this.notificationService.show('Identificamos sua conta PF. Complete seu cadastro para vender.', 'info');
          
          this.enterprise.nome_admin_empresa = userDetails.username;
          this.enterprise.cpf_adm = userDetails.cpf || '';
          
        }

        else if (userDetails.account_type === 'enterprise') {
          this.notificationService.show('Identificamos sua conta PJ. Complete seu cadastro para vender.', 'info');
          
          this.enterprise.cnpj = userDetails.cnpj || '';
          this.enterprise.nome_fantasia = userDetails.username;

        }
      },
      error: (err) => {
        
        this.notificationService.show('Faça login para continuar.', 'error');
        this.authService.logout();
        this.router.navigate(['/']);
      }
    });
  }
  
  onSubmit() {
    if (this.isSubmitting) {
      return; 
    }
    this.isSubmitting = true;

    this.enterpriseService.registerEnterprise(this.enterprise).subscribe({
        next: (response) => {
          console.log('Solicitação de cadastro enviada!', response);
          
          this.notificationService.show(
            'Solicitação enviada com sucesso! Iremos notificá-lo por e-mail quando o seu registo for aprovado.',
            "success"
          );

          this.router.navigate(['/']);
        },
        error: (error) => {
          console.error('Erro ao enviar solicitação de cadastro', error);
          
          const errorMessage = error.error?.detail || 'Ocorreu um erro ao enviar a sua solicitação.';
          this.notificationService.show(errorMessage, "error");
          this.isSubmitting = false; 
        },
        complete: () => {
          this.isSubmitting = false; 
        }
      });
  }
}