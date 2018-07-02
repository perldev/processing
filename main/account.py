import main.models 
from django.contrib.auth.models import User

def get_account(**kawrds):
    return Account(**kawrds)



class Account(object):
    
    def __repr__(self):
        return "%i user %i, currency_id %i, balance %s" % (self.__account.id, self.__account.user_id,self.__account.currency_id, self.__account.balance)
    
    
    def __init__(self, *args, **data):
        user = data.get('user', None)
        currency = data.get('currency', None)
        user_id=data.get('user_id', None)
        id = data.get('id', None)

        if isinstance(user, User):
            user_id = user.id

        if isinstance(user, int):
            user_id = user

        currency_id = data.get('currency_id', None)
        if isinstance(currency, main.models.Currency):
            currency_id = currency.id

        if isinstance(currency, int):
            currency_id = currency


        self.__account = main.models.Accounts.objects.get(user_id = user_id, currency_id=currency_id)
        self.__currency_id = currency_id
        self.__user_id = user_id
        self.__inconsist = False    

        if self.__account.balance != 0 and self.__account.last_trans_id :
            self.__trans = main.models.TransMem.objects.get(id=self.__account.last_trans_id)
            #self.__balance =  self.__trans.res_balance1
            self.__balance = self.__account.balance
        else:
            self.__trans = None
            self.__balance = self.__account.balance
            return 

        
    
    @property
    def currency(self):
        return self.__currency_id

    def acc(self):
        return self.__account

    def get_user(self):
        return self.__user_id

    def reload(self):
        self.__account = main.models.Accounts.objects.get(user_id = self.__user_id, currency_id=self.__currency_id)
        if self.__account.last_trans_id :
            self.__trans = main.models.TransMem.objects.get(id=self.__account.last_trans_id)
        else:
            self.__trans = None
            
        self.__balance = self.__account.balance
        #self.__balance =  self.__trans.res_balance1
        self.__inconsist = False

    @property
    def balance(self):
        return self.__balance
        
    @property
    def get_balance(self):
        if  self.__inconsist :
            raise TransError("it seems a race condition, reload object")
        return self.__balance
    # not used
    def plus(self, amnt):
        self.__balance += amnt
        return  self.__balance
    # not used
    def mines(self, amnt):
        self.__balance -= amnt
        return  self.__balance

    def save(self, trans):
        if  self.__inconsist:
            raise TransError("it seems a race condition, reload object")

        try:
            acc = None
            count = 0
            if  self.__trans :
                count = main.models.Accounts.objects.filter(id=self.__account.id, 
                                                            last_trans_id=self.__trans.id).update(
                                                            last_trans_id=trans.id,
                                                            balance=trans.res_balance1)
            else:
                count = main.models.Accounts.objects.filter(id=self.__account.id).update(
                                                            last_trans_id=trans.id,
                                                            balance=trans.res_balance1)
            if count!=1:
                raise TransError("race condition at account %s" % self)

            self.__trans = trans
        except main.models.Accounts.DoesNotExist:
            raise TransError("it seems a race condition")
            
