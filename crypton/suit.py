# -*- coding: utf-8 -*-

SUIT_CONFIG = {
    # header
    'LIST_PER_PAGE': 200,
    'ADMIN_NAME': 'Stocking',
    'HEADER_DATE_FORMAT': 'l, j. F Y',
    'HEADER_TIME_FORMAT': 'H:i',

    # menu
    'SEARCH_URL': '/admin/auth/user/',
    'MENU_ICONS': {
        'sites': 'icon-leaf',
        'auth': 'icon-lock',
    },
    'MENU_OPEN_FIRST_CHILD': True,

    'MENU': (
        '-',
        {'label': 'Money', 'icon': 'icon-user', 'models': (
            'main.cardp2ptransfers',
            'main.cryptotransfers',
            'main.p24transin',
            'main.liqpaytrans',
          
        )},
        {'label': 'Stock', 'icon': 'icon-user', 'models': (
            'main.ordersmem',
            'main.transmem',
            'main.dealsmemory',
        )},
        {'label': 'Dashboard', 'icon': 'icon-user', 'models': (
            'main.volatileconsts',
            'main.stockstat',
            {'label': 'Баланс системы', 'url': '/admin/main/whole_balance'},
        )},       
       
        
    )
        
}


#'-',
        #{'label': 'Menu', 'icon': 'icon-user', 
            #'models': (
            #'cwist.role',
            #'cwist.family',
            #'cwist.kidprofile',
            #'cwist.parentprofile',
            #{'label': 'Innovators', 'url': '/admin/innovators/'},
            #'cwist.shippingaddress',
            #{'label': 'Whole Balance', 'url': 'main/whole_balance'},
        #)},







