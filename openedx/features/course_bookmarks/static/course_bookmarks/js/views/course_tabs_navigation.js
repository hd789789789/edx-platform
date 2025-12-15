(function(define) {
    'use strict';

    define([
        'jquery',
        'gettext'
    ],
    function($, gettext) {
        /**
         * Fetch course tabs from API and render them similar to app-learning
         */
        var CourseTabsNavigation = function(options) {
            this.courseId = options.courseId;
            this.$container = options.$container;
            // Bookmarks is not a tab, so no tab should be active
            // Or we can make outline tab active by default
            this.activeTabSlug = null; // No active tab for bookmarks page
            this.init();
        };

        CourseTabsNavigation.prototype = {
            init: function() {
                var self = this;
                this.fetchTabs().done(function(tabs) {
                    self.renderTabs(tabs);
                }).fail(function() {
                    // If API fails, try to get tabs from Django template
                    self.renderFallbackTabs();
                });
            },

            fetchTabs: function() {
                var self = this;
                var apiUrl = '/api/course_home/v1/course_metadata/' + this.courseId;
                
                return $.ajax({
                    url: apiUrl,
                    type: 'GET',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': $('[name=csrfmiddlewaretoken]').val() || $('meta[name=csrf-token]').attr('content')
                    }
                }).then(function(data) {
                    return self.normalizeTabs(data.tabs || []);
                });
            },

            normalizeTabs: function(tabs) {
                var self = this;
                var courseId = this.courseId;
                
                // Process tabs similar to LoadedTabPage.jsx
                var welcomeTab = {
                    title: '👋 Chào mừng',
                    slug: 'welcome',
                    url: '/learning/course/' + courseId + '/welcome'
                };

                var badgeTab = {
                    title: '🏅 Thành tích',
                    slug: 'badge',
                    url: '/learning/course/' + courseId + '/badge'
                };

                // Filter and map tabs
                var tabsCopy = tabs
                    .filter(function(tab) {
                        return tab.tab_id !== 'progress' && 
                               tab.tab_id !== 'dates' && 
                               tab.tab_id !== 'discussion';
                    })
                    .map(function(tab) {
                        var slug = tab.tab_id === 'courseware' ? 'outline' : tab.tab_id;
                        var title = tab.title;
                        var url = tab.url;

                        // Update title for outline tab
                        if (slug === 'outline') {
                            title = '📚 Khóa học';
                        }

                        // Update title for leaderboard tab
                        if (slug === 'leaderboard') {
                            title = '🏆 Xếp hạng';
                        }

                        // Update teams tab
                        if (slug === 'teams') {
                            title = 'Nhóm';
                            if (url && url.includes('/courses/') && url.includes('/teams_dashboard')) {
                                url = '/learning/course/' + courseId + '/teams';
                            } else if (!url || (!url.includes('/learning/') && !url.includes('/course/'))) {
                                url = '/learning/course/' + courseId + '/teams';
                            }
                        }

                        return {
                            slug: slug,
                            title: title,
                            url: url
                        };
                    });

                // Add badge tab before leaderboard
                var leaderboardIndex = tabsCopy.findIndex(function(tab) {
                    return tab.slug === 'leaderboard';
                });
                if (leaderboardIndex !== -1) {
                    tabsCopy.splice(leaderboardIndex, 0, badgeTab);
                } else {
                    tabsCopy.push(badgeTab);
                }

                // Add welcome tab at the beginning
                tabsCopy.unshift(welcomeTab);

                return tabsCopy;
            },

            renderTabs: function(tabs) {
                var self = this;
                var $nav = $('<div>', {
                    id: 'courseTabsNavigation',
                    class: 'course-tabs-navigation mb-3'
                });

                var $container = $('<div>', {
                    class: 'container-xl'
                });

                var $navBar = $('<div>', {
                    class: 'nav-bar'
                });

                var $navMenu = $('<div>', {
                    class: 'nav-menu'
                });

                var $tabs = $('<nav>', {
                    class: 'nav flex-nowrap nav-underline-tabs',
                    'aria-label': 'Course Material'
                });

                // Render each tab
                tabs.forEach(function(tab) {
                    // Check if current URL matches this tab's URL to determine active state
                    var currentPath = window.location.pathname;
                    var tabPath = tab.url;
                    // Remove trailing slashes for comparison
                    currentPath = currentPath.replace(/\/$/, '');
                    tabPath = tabPath.replace(/\/$/, '');
                    
                    // On bookmarks page, highlight the "Khóa học" (outline) tab
                    var isActive = false;
                    if (currentPath.includes('/bookmarks')) {
                        // If we're on bookmarks page, make outline tab active
                        isActive = tab.slug === 'outline';
                    } else {
                        // Otherwise, check if URL matches
                        isActive = currentPath === tabPath;
                    }
                    
                    var $link = $('<a>', {
                        href: tab.url,
                        class: 'nav-item flex-shrink-0 nav-link' + (isActive ? ' active' : ''),
                        text: tab.title
                    });
                    $tabs.append($link);
                });

                $navMenu.append($tabs);
                $navBar.append($navMenu);
                $container.append($navBar);
                $nav.append($container);

                // Replace or append to container
                this.$container.html($nav);
            },

            renderFallbackTabs: function() {
                // Fallback: try to get tabs from existing navigation if available
                var $existingNav = $('.course-tabs, .navbar.course-tabs');
                if ($existingNav.length > 0) {
                    // Just show existing navigation
                    return;
                }
                // If no existing navigation, show minimal tabs
                this.$container.html('<div class="course-tabs-navigation mb-3"><div class="container-xl"><nav class="nav flex-nowrap nav-underline-tabs"><a href="/learning/course/' + this.courseId + '/home" class="nav-item flex-shrink-0 nav-link">📚 Khóa học</a></nav></div></div>');
            }
        };

        return CourseTabsNavigation;
    });
}).call(this, define || RequireJS.define);

