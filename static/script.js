import Navbar from './components/Navbar.js'
import Foot from './components/Footer.js'
import Home from './components/Home.js'
import Login from './components/Login.js'
import Register from './components/Register.js'
import Admin_dashboard from './components/Admin_dashboard.js'
import Profile from './components/Profile.js'
import Admin_users from './components/Admin_users.js'
import Admin_summary from './components/Admin_summary.js'
import Admin_search from './components/Admin_search.js'
import Create_lot from './components/Create_lot.js'
import View_lot from './components/View_lot.js'
import Edit_lot from './components/Edit_lot.js'
import View_spot from './components/View_spot.js'
import User_dashboard from './components/User_dashboard.js'
import User_summary from './components/User_summary.js'
import Book_spot from './components/Book_spot.js'
import Release_spot from './components/Release_spot.js'

const routes = [
    { path: '/', name: 'home_page', component: Home },
    { path: '/login', name: 'login_page', component: Login },
    { path: '/register', name: 'register_page', component: Register },
    { path: '/admin/dashboard', name: 'admin_dashboard_page', component: Admin_dashboard },
    { path: '/admin/users', name: 'admin_users_page', component: Admin_users },
    { path: '/admin/search', name: 'admin_search_page', component: Admin_search },
    { path: '/admin/summary', name: 'admin_summary_page', component: Admin_summary },
    { path: '/admin/:user_id/profile', name: 'admin_profile', component: Profile },
    { path: '/admin/parking_lot/create', name: 'create_parking_lot_page', component: Create_lot },
    { path: '/admin/parking_lot/:id', name: 'view_parking_lot_page', component: View_lot },
    { path: '/admin/parking_lot/:id/edit', name: 'edit_parking_lot_page', component: Edit_lot },
    { path: '/admin/parking_lot/:lot_id/spots/:spot_id', name: 'view_spot_page', component: View_spot },
    { path: '/user/:user_id/dashboard', name: 'user_dashboard_page', component: User_dashboard },
    { path: '/user/:user_id/summary', name: 'user_summary_page', component: User_summary },
    { path: '/user/:user_id/profile', name: 'user_profile', component: Profile },
    { path: '/user/:user_id/book/:lot_id', name: 'book_spot_page', component: Book_spot },
    { path: '/user/:user_id/release/:reservation_id', name: 'release_spot_page', component: Release_spot },
]

const router = new VueRouter({
    mode: 'history',
    routes 
})

const app = new Vue({
    el: '#app',
    router,
    template: `
        <div class="container d-flex flex-column min-vh-100">
            <nav-bar :loggedIn = 'loggedIn' :userRole = 'userRole' :userID='userID'  @logout="handlelogout"></nav-bar>
            <div class="flex-grow-1">
            <router-view :loggedIn = 'loggedIn' @login="handlelogin"></router-view>
            </div>
            <foot></foot>
        </div>
    `,
    data: {
        loggedIn: null,
        userID: null,
        userRole: null
    },
    components: {
        'nav-bar': Navbar,
        foot: Foot
    },
    mounted() {
        if (localStorage.getItem('auth_token')) {
            this.loggedIn = true
            this.getDetails()
        } else {
            this.loggedIn = false
        }
    },
    methods: {
        getDetails() {
            fetch('/api/user_details', {
                method: 'GET',
                headers: {
                    "Authentication-Token": localStorage.getItem("auth_token")
                }
            }).then(response => response.json())
                .then(data => {
                    if (data) {
                        this.userRole = data.role
                        this.userID = data.user_id
                    } else {
                        console.log(data.error)
                    }
                })
        },
        handlelogout() {
            localStorage.clear()
            this.loggedIn = false
            this.userRole = null
            this.userID = null
        },
        handlelogin() {
            this.loggedIn = true
            this.getDetails()
        }
    }

})